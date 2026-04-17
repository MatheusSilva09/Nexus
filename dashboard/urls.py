from django.urls import path
from . import views

urlpatterns = [
    # Rota principal do painel (Nexus Control)
    path('', views.home, name='home'),
    
    # Rota para a listagem de estoque
    path('estoque/', views.lista_estoque, name='lista_estoque'),
    
    # Rota para atualizar a quantidade (recebe o ID do produto)
    path('estoque/atualizar/<int:produto_id>/', views.atualizar_quantidade_estoque, name='atualizar_estoque'),
    
    # Rota para o checkout (Nexus Shop)
    path('checkout/finalizar/', views.finalizar_pedido, name='finalizar_pedido'),
]