# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2019-09-04 21:32


from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


def insert_data(apps, schema_editor):
    # We can't import the Person model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    DesignSafeProfileNHInterests = apps.get_model("designsafe_accounts", "DesignSafeProfileNHInterests")
    data = [
      "Coastal engineering",
      "Earthquake",
      "Geotechnical",
      "Lifeline infrastructure",
      "Social sciences and/or policy",
      "Tsunami",
      "Wind"
    ]
    for d in data:
        obj = DesignSafeProfileNHInterests(description=d)
        obj.save()


def add_research_activities_data(apps, schema_editor):
    DesignSafeProfileResearchActivities = apps.get_model("designsafe_accounts", "DesignSafeProfileResearchActivities")
    data = [
      "Already performed research in the NHERI program",
      "Performed research in the NEES program",
      "Performed research in the NHERI subject area but not in the NEES or NHERI programs",
      "Planning to perform research in the NHERI program",
      "Involved in education in the NHERI subject areas",
      "No direct involvement in reseach or education in the NHERI subject areas"
    ]
    for d in data:
        obj = DesignSafeProfileResearchActivities(description=d)
        obj.save()


def set_default_notification_prefs(apps, schema_editor):
    # Find users with no prefs set
    User = apps.get_model(settings.AUTH_USER_MODEL)
    NotificationPreferences = apps.get_model(
        "designsafe_accounts", "NotificationPreferences")
    users = User.objects.filter(Q(notification_preferences__isnull=True))
    for user in users:
        prefs = NotificationPreferences(user=user)
        prefs.save()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DesignSafeProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ethnicity', models.CharField(max_length=255)),
                ('gender', models.CharField(max_length=255)),
                ('agree_to_account_limit', models.DateTimeField(auto_now_add=True, null=True)),
                ('bio', models.CharField(blank=True, default=None, max_length=4096, null=True)),
                ('website', models.CharField(blank=True, default=None, max_length=256, null=True)),
                ('orcid_id', models.CharField(blank=True, default=None, max_length=256, null=True)),
                ('professional_level', models.CharField(default=None, max_length=256, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='DesignSafeProfileNHInterests',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=300)),
            ],
        ),
        migrations.CreateModel(
            name='DesignSafeProfileResearchActivities',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=300)),
            ],
        ),
        migrations.CreateModel(
            name='NotificationPreferences',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('announcements', models.BooleanField(default=True, verbose_name='Announcements: to communicate EF Workshops, NHERI Newsletter, Student Opportunities, etc.')),
                ('tutorials', models.BooleanField(default=True, verbose_name='Tutorials: to communicate DesignSafe training opportunities.')),
                ('designsafe', models.BooleanField(default=True, verbose_name='DesignSafe: to communicate new features, planned outages.')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification_preferences', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'permissions': (('view_notification_subscribers', 'Can view list of users subscribed to a notification type'),),
            },
        ),
        migrations.AddField(
            model_name='designsafeprofile',
            name='nh_interests',
            field=models.ManyToManyField(to='designsafe_accounts.DesignSafeProfileNHInterests'),
        ),
        migrations.AddField(
            model_name='designsafeprofile',
            name='research_activities',
            field=models.ManyToManyField(to='designsafe_accounts.DesignSafeProfileResearchActivities'),
        ),
        migrations.AddField(
            model_name='designsafeprofile',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(
            code=insert_data,
        ),
        migrations.RunPython(
            code=add_research_activities_data,
        ),
        migrations.RunPython(
            code=set_default_notification_prefs,
        ),
    ]