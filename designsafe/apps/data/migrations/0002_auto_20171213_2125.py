# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-12-13 21:25
from __future__ import unicode_literals
from elasticsearch_dsl import Q
from elasticsearch import TransportError
from designsafe.libs.elasticsearch import docs as DocsManager

from django.db import migrations

def reindex_files(*args):
    pass

def reindex_publications(*args):
    pass

def reindex_nees_projects(*args):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('data', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(reindex_nees_projects),
        migrations.RunPython(reindex_publications),
    ]