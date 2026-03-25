from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('resources', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CloudStorageAccount',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('provider', models.CharField(choices=[('google_drive', 'Google Drive'), ('onedrive', 'OneDrive')], max_length=20)),
                ('provider_user_id', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254)),
                ('display_name', models.CharField(max_length=255)),
                ('avatar_url', models.URLField(blank=True, null=True)),
                ('access_token', models.TextField()),
                ('refresh_token', models.TextField(blank=True, null=True)),
                ('token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('storage_used', models.BigIntegerField(default=0)),
                ('storage_total', models.BigIntegerField(default=0)),
                ('last_sync', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cloud_storage_accounts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'cloud_storage_accounts',
                'ordering': ['-created_at'],
                'unique_together': {('user', 'provider')},
            },
        ),
        migrations.CreateModel(
            name='CloudFile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('provider_file_id', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=255)),
                ('mime_type', models.CharField(max_length=255)),
                ('size', models.BigIntegerField(default=0)),
                ('modified_time', models.DateTimeField(blank=True, null=True)),
                ('web_url', models.URLField(blank=True, null=True)),
                ('download_url', models.URLField(blank=True, null=True)),
                ('is_folder', models.BooleanField(default=False)),
                ('parent_folder_id', models.CharField(blank=True, max_length=255, null=True)),
                ('cached_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='cloud_storage.cloudstorageaccount')),
            ],
            options={
                'db_table': 'cloud_files',
                'ordering': ['-cached_at'],
                'unique_together': {('account', 'provider_file_id')},
            },
        ),
        migrations.CreateModel(
            name='CloudExportHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('cloud_file_id', models.CharField(max_length=255)),
                ('cloud_file_name', models.CharField(max_length=255)),
                ('exported_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exports', to='cloud_storage.cloudstorageaccount')),
                ('resource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cloud_exports', to='resources.resource')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cloud_exports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'cloud_export_history',
                'ordering': ['-exported_at'],
            },
        ),
        migrations.CreateModel(
            name='CloudImportHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('imported_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='imports', to='cloud_storage.cloudstorageaccount')),
                ('cloud_file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='imports', to='cloud_storage.cloudfile')),
                ('resource', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='cloud_imports', to='resources.resource')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cloud_imports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'cloud_import_history',
                'ordering': ['-imported_at'],
            },
        ),
    ]

