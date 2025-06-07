from django.contrib.auth.models import User
from rest_framework import viewsets, permissions, status
from rest_framework.generics import RetrieveAPIView
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import DocumentCategory, DocumentTemplate, GeneratedDocument
from .serializers import (
    UserSerializer, DocumentCategorySerializer,
    DocumentTemplateSerializer, GeneratedDocumentSerializer
)

# Imports for WeasyPrint generation
from django.conf import settings
from django.template.loader import get_template
from weasyprint import HTML
import os
from datetime import date # For generation date in footer


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    # permission_classes are globally set to IsAuthenticated via settings.py

class CurrentUserView(RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated] # Explicit for this view

    def get_object(self):
        return self.request.user

class DocumentCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DocumentCategory.objects.all().order_by('name')
    serializer_class = DocumentCategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'

class DocumentTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DocumentTemplateSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = DocumentTemplate.objects.filter(is_active=True).order_by('name', '-version')
        category_slug_param = self.request.query_params.get('category_slug')
        if category_slug_param:
            queryset = queryset.filter(category__slug=category_slug_param)
        return queryset

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def generate_document(self, request, slug=None):
        '''
        Génère un document basé sur ce template et les données fournies.
        '''
        template = self.get_object() # Récupère le DocumentTemplate par son slug
        user = request.user
        input_data = request.data.get('input_data', {})

        # Étape 1: Validation basique des input_data
        if not isinstance(input_data, dict) or not input_data:
            return Response(
                {"error": "input_data (dictionnaire non vide) est requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        required_fields_from_def = []
        if isinstance(template.form_definition, dict) and 'fields' in template.form_definition:
            for field_def in template.form_definition.get('fields', []):
                if field_def.get('required', False):
                    field_name = field_def.get('name')
                    if field_name: # Ensure field_name is not None
                         required_fields_from_def.append(field_name)

        missing_fields = [rf for rf in required_fields_from_def if rf not in input_data]
        if missing_fields:
            return Response(
                {"error": f"Champs manquants dans input_data: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Étape 2: Créer l'objet GeneratedDocument (avant la génération effective)
        generated_doc = GeneratedDocument.objects.create(
            user=user,
            document_template=template,
            template_version_at_generation=template.version,
            input_data=input_data,
            status='generating' # Mettre à jour le statut
        )

        try:
            # Étape 3: Vraie génération du document avec WeasyPrint
            template_name_from_path = template.template_file_path
            if not template_name_from_path:
                # Fallback ou logique pour déterminer le template si non défini directement
                # Pour cette démo, on peut supposer un template par défaut ou lever une erreur
                # Ou utiliser une clé dans input_data comme 'template_name_override'
                # Si template.template_file_path est vide, cela indique une configuration manquante.
                # Il est préférable de lever une erreur ou d'avoir une logique claire ici.
                # Pour la démo, on utilise un chemin fixe comme dans la demande initiale
                # if not template_name_from_path: template_name_from_path = input_data.get('template_name_override', 'api/document_templates/simple_letter.html')
                # Pour une meilleure robustesse, on devrait s'assurer que template.template_file_path est toujours défini.
                # L'instruction originale était :
                # template_name_from_path = input_data.get('template_name_override', 'api/document_templates/simple_letter.html')
                # Cela semble être une mauvaise pratique de laisser input_data surcharger le template.
                # S'il n'est pas défini dans le modèle, il faudrait une erreur ou un default strict.
                # Pour l'instant, on va supposer que template.template_file_path est valide.
                # Si ce champ est vide sur le modèle, il faut une erreur.
                if not template.template_file_path:
                    generated_doc.status = 'failed'
                    generated_doc.error_message = "Chemin du fichier modèle non configuré dans DocumentTemplate."
                    generated_doc.save()
                    return Response(
                        {"error": "Configuration du modèle de document incomplète: chemin du fichier modèle manquant."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR # ou 400 si on considère que c'est une erreur client de demander un template non configurable
                    )
                template_name_from_path = template.template_file_path


            # Contexte pour le template HTML
            context = input_data.copy()
            context['generation_date'] = date.today().strftime("%d/%m/%Y")
            # context['user'] = user # Passer l'objet utilisateur si besoin

            # Rendre le template HTML
            html_template = get_template(template_name_from_path)
            html_string = html_template.render(context)

            # Générer le PDF avec WeasyPrint
            output_folder = os.path.join(settings.MEDIA_ROOT, 'generated_documents', user.username.replace('@','_at_').replace('.', '_'), template.slug)
            os.makedirs(output_folder, exist_ok=True)

            # Sanitize filename parts further if necessary
            safe_slug = template.slug.replace('/', '_')
            safe_username = user.username.replace('@','_at_').replace('.', '_')
            pdf_filename = f"{generated_doc.id}_{safe_slug}_{safe_username}.pdf"
            pdf_output_path = os.path.join(output_folder, pdf_filename)

            HTML(string=html_string).write_pdf(pdf_output_path)

            generated_doc.file_path = os.path.relpath(pdf_output_path, settings.MEDIA_ROOT)
            generated_doc.status = 'completed'
            generated_doc.save()

            serializer = GeneratedDocumentSerializer(generated_doc)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            generated_doc.status = 'failed'
            generated_doc.error_message = str(e)
            generated_doc.save()
            print(f"Erreur de génération de document (ID: {generated_doc.id}): {e}")
            return Response(
                {"error": "Erreur lors de la génération du document.", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
