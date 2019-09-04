# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2019-09-04 20:31
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import oauth2client.contrib.django_util.models
from google.oauth2.credentials import Credentials


# Functions from the following migrations need manual copying.
# Move them and any dependencies into this file, then update the
# RunPython operations to refer to the local versions:
# designsafe.apps.googledrive_integration.migrations.0002_auto_20180215_2239


def create_credential_model(apps, schema_editor):
    # Find users that already have Google Drive access set up,
    # and consolidate tokens into CredentialsField model

    GoogleDriveUserToken = apps.get_model(
        "googledrive_integration", "GoogleDriveUserToken")
    tokens = GoogleDriveUserToken.objects.all()
    for google_token in tokens:
        credentials = {
            'token': google_token.token,
            'refresh_token': google_token.refresh_token,
            'token_uri': google_token.token_uri,
            'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
            'client_secret': settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            'scopes': [google_token.scopes]
        }
        
        google_token.credential = Credentials(**credentials)
        google_token.save()

        # google_token.delete()
        # token = GoogleDriveUserToken(
        #     user=google_token.user,
        #     credentials=Credentials(**credentials)
        # )

        # token.save()


class Migration(migrations.Migration):

    replaces = [(b'googledrive_integration', '0001_initial'), (b'googledrive_integration', '0002_auto_20180215_2239')]

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GoogleDriveUserToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=255)),
                ('refresh_token', models.CharField(max_length=255)),
                ('token_uri', models.CharField(max_length=255)),
                ('scopes', models.CharField(max_length=255)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='googledrive_user_token', to=settings.AUTH_USER_MODEL)),
                ('credential', oauth2client.contrib.django_util.models.CredentialsField(null=True)),
            ],
        ),
        migrations.RunPython(
            code=create_credential_model,
        ),
        migrations.RemoveField(
            model_name='googledriveusertoken',
            name='refresh_token',
        ),
        migrations.RemoveField(
            model_name='googledriveusertoken',
            name='scopes',
        ),
        migrations.RemoveField(
            model_name='googledriveusertoken',
            name='token',
        ),
        migrations.RemoveField(
            model_name='googledriveusertoken',
            name='token_uri',
        ),
    ]