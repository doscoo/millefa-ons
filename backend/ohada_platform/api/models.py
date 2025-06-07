from django.db import models
from django.contrib.auth.models import User # Si on veut lier des templates à des utilisateurs/créateurs
from django.utils.text import slugify

class DocumentCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    # Ajout de slug pour des URLs plus propres
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Catégorie de document"
        verbose_name_plural = "Catégories de documents"

class DocumentTemplate(models.Model):
    category = models.ForeignKey(DocumentCategory, related_name='templates', on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    # slug pour des URLs plus propres pour les templates aussi
    slug = models.SlugField(max_length=270, unique=True, blank=True)

    # Ce champ stockera la structure du formulaire, ex: JSONField
    # Pour JSONField, sur PostgreSQL, c'est natif. Sur SQLite, Django simule.
    form_definition = models.JSONField(default=dict, help_text="Définition JSON du formulaire pour ce modèle.")

    # Chemin vers le fichier modèle physique (ex: .docx, .html)
    # Ce chemin pourrait être relatif à un répertoire MEDIA_ROOT/templates_files/
    template_file_path = models.CharField(max_length=500, blank=True, null=True, help_text="Chemin vers le fichier modèle (ex: 'docx_templates/contrat_bail.docx')")

    ohada_compliance_details = models.TextField(blank=True, null=True, help_text="Détails sur la conformité OHADA.")
    version = models.CharField(max_length=20, default='1.0')
    is_active = models.BooleanField(default=True, help_text="Indique si ce modèle est activement proposé aux utilisateurs.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # created_by = models.ForeignKey(User, related_name='document_templates_created', on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            # Ensure slug is unique, append version if needed, or handle more robustly
            base_slug = slugify(self.name)
            unique_slug = base_slug
            # This simple increment might not be robust enough for all cases (e.g. if versions are not sequential or if names can be very similar)
            # A more robust solution might involve checking existence in a loop and appending a counter or part of the version.
            # For now, assuming name + version uniqueness will largely handle this via unique_together in Meta.
            # If slug needs to be globally unique even across different versions, this needs refinement.
            # For this iteration, we'll keep it simple: slugify the name. The unique=True on SlugField will enforce uniqueness.
            # If a conflict occurs, the database will raise an IntegrityError.
            # A common pattern is to slugify name + version, or name + short_uuid.
            self.slug = slugify(f"{self.name}-{self.version}") # Make slug more unique by default including version
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (v{self.version})"

    class Meta:
        verbose_name = "Modèle de document"
        verbose_name_plural = "Modèles de documents"
        ordering = ['name', '-version']
        # Unicité sur nom et version pour permettre plusieurs versions d'un même template
        unique_together = (('name', 'version'),)


class GeneratedDocument(models.Model):
    user = models.ForeignKey(User, related_name='generated_documents', on_delete=models.CASCADE)
    document_template = models.ForeignKey(DocumentTemplate, related_name='generated_instances', on_delete=models.PROTECT) # Protéger si un template est référencé

    # Données d'entrée fournies par l'utilisateur pour ce document spécifique
    # Il est fortement recommandé de chiffrer ces données si elles sont sensibles.
    # Pour l'instant, nous les stockons en JSON. Le chiffrement est une amélioration future.
    input_data = models.JSONField(help_text="Données fournies par l'utilisateur pour générer ce document.")

    # Chemin vers le fichier de document généré (ex: dans un stockage cloud comme S3)
    # Ce chemin sera relatif à MEDIA_ROOT ou à une configuration de stockage cloud.
    file_path = models.CharField(max_length=1024, blank=True, null=True, help_text="Chemin vers le fichier de document généré.")

    # Statut du document
    STATUS_CHOICES = [
        ('pending', 'En attente de génération'),
        ('generating', 'Génération en cours'),
        ('completed', 'Terminé'),
        ('failed', 'Échec de la génération'),
        ('archived', 'Archivé'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Détails en cas d'erreur de génération
    error_message = models.TextField(blank=True, null=True)

    # Version du template utilisé pour générer ce document
    template_version_at_generation = models.CharField(max_length=20, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Document {self.id} (User: {self.user.username}, Template: {self.document_template.name} v{self.document_template.version})"

    class Meta:
        verbose_name = "Document Généré"
        verbose_name_plural = "Documents Générés"
        ordering = ['-created_at']
