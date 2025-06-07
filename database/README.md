# Database

## SGBD choisi

PostgreSQL

## Entités principales à modéliser

- **User**:
    - id (primaire)
    - email (unique)
    - password_hash (ou référence à Auth0 id)
    - created_at
    - updated_at
- **DocumentTemplate**:
    - id (primaire)
    - name
    - description
    - category_id (foreign key vers DocumentCategory)
    - form_schema (JSON définissant les champs du template)
    - created_at
    - updated_at
- **GeneratedDocument**:
    - id (primaire)
    - user_id (foreign key vers User)
    - template_id (foreign key vers DocumentTemplate)
    - data (JSON contenant les informations remplies par l'utilisateur)
    - storage_path (chemin vers le document généré sur S3)
    - generated_at
    - accessed_at
- **DocumentCategory**:
    - id (primaire)
    - name (unique)
    - description

## ORM

Utilisation de l'ORM Django.
