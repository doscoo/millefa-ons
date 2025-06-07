from django.contrib.auth.models import User
from rest_framework import serializers
from .models import DocumentCategory, DocumentTemplate, GeneratedDocument # Ajout de GeneratedDocument

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class DocumentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentCategory
        fields = ['id', 'name', 'slug', 'description']

class DocumentTemplateSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)

    class Meta:
        model = DocumentTemplate
        fields = [
            'id', 'name', 'slug', 'description',
            'category', 'category_name', 'category_slug', # category field is for writing, _name and _slug for reading
            'form_definition',
            'ohada_compliance_details', 'version', 'is_active',
            'created_at', 'updated_at', 'template_file_path' # Added template_file_path
        ]
        read_only_fields = ['created_at', 'updated_at', 'category_name', 'category_slug']
        # Make category field write_only if it's only used for linking on create/update
        # and category_name/category_slug are used for representation.
        # However, standard practice is to allow sending category ID for writing.
        # If 'category' is sent as an ID, DRF handles it.
        # If you want to create/update by slug, you might need a SlugRelatedField for 'category'.
        # For now, this setup allows sending category ID and getting details back.
        extra_kwargs = {
            'category': {'write_only': False, 'required': True} # Example: ensure category is provided
        }


class GeneratedDocumentSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    document_template_name = serializers.CharField(source='document_template.name', read_only=True)
    document_template_version = serializers.CharField(source='document_template.version', read_only=True)


    class Meta:
        model = GeneratedDocument
        fields = [
            'id', 'user', 'user_username',
            'document_template', 'document_template_name', 'document_template_version',
            'template_version_at_generation', # Version stored at generation time
            'input_data', 'file_path',
            'status', 'error_message',
            'created_at', 'updated_at'
        ]
        # Most fields are read_only because they are set by the server during generation
        # or are immutable after creation.
        # 'input_data' is the primary field expected from the client on creation (via the custom action).
        read_only_fields = [
            'id', 'user', 'user_username',
            'document_template', 'document_template_name', 'document_template_version',
            'template_version_at_generation', # This is set by the server
            'file_path', 'status', 'error_message',
            'created_at', 'updated_at'
        ]
        # For creation via the custom action, only 'input_data' would be implicitly expected in request.data
        # The serializer itself is mostly for representation here.
        # If we had a direct ViewSet for GeneratedDocument (e.g. for listing/retrieving),
        # this serializer would be used.
        # The 'generate_document' action handles creation more directly.
