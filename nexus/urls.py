"""
URL configuration for nexus project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from dashboard import views
from loja import views as loja_views

urlpatterns = [
    # Rota universal e direta para o Favicon (Evita problemas de carregamento no Django 6.0)
    path('favicon.ico', RedirectView.as_view(url='/static/img/favicon_nexushub.png')),

    # Nova rota customizada para o Nexus Hub Login: http://127.0.0.1:8000/nexushub/
    path('nexushub/', views.login_view, name='login_view'),

    # Redireciona a raiz (/) e a rota antiga /login/ para a nova URL personalizada
    path('', RedirectView.as_view(pattern_name='login_view'), name='index_redirect'),
    path('login/', RedirectView.as_view(pattern_name='login_view'), name='login_fix'),

    # Redirecionamentos de Legado: Captura a estrutura antiga e joga para a nova
    path('nexusstore/dashboard/login/', RedirectView.as_view(pattern_name='login_view'), name='old_login_redirect'),
    path('nexusstore/dashboard/', RedirectView.as_view(url='/nexushub/dashboard/'), name='old_dashboard_root_redirect'),
    path('nexusstore/dashboard/<path:extra>', RedirectView.as_view(url='/nexushub/dashboard/%(extra)s'), name='old_dashboard_path_redirect'),

    # Rota específica para cadastro da NEXUS Store
    path('nexusstore/dashboard/registrar/', loja_views.loja_cadastro_view, name='loja_cadastro_store'),
    
    path('admin/', admin.site.urls),
    path('accounts/profile/', views.profile, name='profile'),
    
    # A NEXUS Store agora possui seu próprio prefixo independente
    path('nexusstore/', include('loja.urls')),
    
    # O ecossistema NEXUS Hub (Dashboard e Gestão) agora fica sob /nexushub/
    path('nexushub/', include('dashboard.urls')),
]

# Serve arquivos de mídia durante o desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)