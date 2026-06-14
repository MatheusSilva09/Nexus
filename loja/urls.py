from django.urls import path
from . import views

urlpatterns = [
    path('', views.vitrine_view, name='vitrine'),
    path('carrinho/adicionar/<int:produto_id>/', views.adicionar_ao_carrinho_view, name='adicionar_ao_carrinho'),
    path('carrinho/', views.ver_carrinho_view, name='ver_carrinho'),
    path('carrinho/remover/<int:produto_id>/', views.remover_do_carrinho_view, name='remover_do_carrinho'),
    path('carrinho/finalizar/', views.finalizar_pedido_view, name='finalizar_pedido'),
    
    # Novas rotas de autenticação da loja
    path('conta/login/', views.loja_login_view, name='loja_login'),
    path('conta/cadastro/', views.loja_cadastro_view, name='loja_cadastro'),
    path('conta/logout/', views.loja_logout_view, name='loja_logout'),
    path('conta/meus-pedidos/', views.loja_meus_pedidos_view, name='loja_meus_pedidos'),
    path('produto/<int:produto_id>/', views.detalhe_produto_loja_view, name='detalhe_produto_loja'),
    path('carrinho/pedido/<int:pedido_id>/cancelar/', views.cancelar_pedido_view, name='cancelar_pedido'),
]