# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2020-04-23 19:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appdescription',
            name='appDescription',
            field=models.TextField(help_text='App dropdown description text for apps that have a dropdown.'),
        ),
    ]
