from django.contrib import admin
from .models import DocumentCategory, DocumentTemplate, GeneratedDocument # Ajout de GeneratedDocument

@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'description')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)} # Pour aider à remplir le slug

@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'category', 'version', 'is_active', 'created_at', 'updated_at')
    list_filter = ('category', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'category__name')
    prepopulated_fields = {'slug': ('name',)} # Will need adjustment due to version in slug
    # Rendre form_definition plus lisible si possible, ou utiliser un widget custom plus tard
    # fields = (('name', 'version'), 'slug', 'category', 'description', 'form_definition', 'template_file_path', 'ohada_compliance_details', 'is_active')
    # readonly_fields = ('created_at', 'updated_at')

    def get_prepopulated_fields(self, request, obj=None):
        # Override to handle slug generation based on name and version
        if obj and obj.name and obj.version and not obj.slug:
             # This won't dynamically update in admin as you type name/version before first save.
             # Slug is now auto-generated on model save if not provided.
             # For admin, prepopulated_fields works best on fields directly typed.
             # We will rely on the model's save() method for slug generation primarily.
             pass
        return {'slug': ('name',)} # Keep basic prepopulation, model's save() will refine.


@admin.register(GeneratedDocument)
class GeneratedDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_email', 'document_template_name_version', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'document_template__category', 'created_at', 'user') # Added user to filter
    search_fields = ('user__username', 'user__email', 'document_template__name', 'id')
    readonly_fields = ('created_at', 'updated_at', 'input_data', 'file_path', 'error_message', 'template_version_at_generation', 'user', 'document_template')

    fieldsets = (
        (None, {
            'fields': ('user', 'document_template', 'status')
        }),
        ('Détails de Génération', {
            'fields': ('template_version_at_generation', 'input_data', 'file_path', 'error_message'),
            'classes': ('collapse',), # Pour cacher par défaut les détails techniques
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def document_template_name_version(self, obj):
        return f"{obj.document_template.name} (v{obj.document_template.version})"
    document_template_name_version.short_description = 'Modèle de Document'

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email Utilisateur'
