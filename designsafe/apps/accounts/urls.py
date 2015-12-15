from django.conf.urls import patterns, include, url

urlpatterns = patterns('designsafe.apps.accounts.views',
    url(r'^$', 'index', name='index'),
    url(r'^register/$', 'register', name='register'),
    url(r'^departments\.json$', 'departments_json', name='departments_json'),
    url(r'^notifications/$', 'notifications', name='notifications'),
)