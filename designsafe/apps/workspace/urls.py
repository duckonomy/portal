"""Workspace urls."""

from django.urls import path, re_path
from designsafe.apps.workspace import views

app_name = "workspace"
urlpatterns = [
    re_path(r'^api/(?P<service>[a-z]+?)/$', views.call_api, name='call_api'),
    re_path(r'^notification/process/(?P<pk>\d+)', views.process_notification, name='process_notification'),
    path('', views.index, name='index'),
]
