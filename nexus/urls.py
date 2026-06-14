from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from dashboard import views as dash_views
from loja import views as loja_views

urlpatterns = [
    # Favicon
    path('favicon.ico', RedirectView.as_view(url='/static/img/favicon_nexushub.png')),

    # Rotas de Autenticação e Raiz
    path('nexushub/login/', dash_views.login_view, name='login_view'),
    path('', RedirectView.as_view(pattern_name='login_view'), name='index_redirect'),
    path('login/', RedirectView.as_view(pattern_name='login_view'), name='login_fix'),

    # Redirecionamentos de Legado
    path('nexusstore/dashboard/login/', RedirectView.as_view(pattern_name='login_view'), name='old_login_redirect'),
    path('nexusstore/dashboard/', RedirectView.as_view(url='/nexushub/dashboard/'), name='old_dashboard_root_redirect'),
    path('nexusstore/dashboard/<path:extra>', RedirectView.as_view(url='/nexushub/dashboard/%(extra)s'), name='old_dashboard_path_redirect'),

    # Rota específica de cadastro da loja
    path('nexusstore/dashboard/registrar/', loja_views.loja_cadastro_view, name='loja_cadastro_store'),
    
    path('admin/', admin.site.urls),
    path('accounts/profile/', dash_views.profile, name='profile'),
    
    # Prefixos principais (Separados para evitar conflitos)
    path('nexusstore/', include('loja.urls')),
    path('nexushub/', include('dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)