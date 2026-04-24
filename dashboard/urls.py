from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('estoque/', views.lista_estoque, name='lista_estoque'),
    
    # Nova rota para o formulário manual que você criou
    path('estoque/novo/', views.adicionar_produto, name='adicionar_produto'),
    
    path('estoque/atualizar/<int:produto_id>/', views.atualizar_quantidade_estoque, name='atualizar_estoque'),
    path('checkout/finalizar/', views.finalizar_pedido, name='finalizar_pedido'),
    path('estoque/editar/<int:produto_id>/', views.editar_produto, name='editar_produto'),
    path('venda/<int:produto_id>/', views.realizar_venda, name='realizar_venda'),
    path('loja/criar/', views.criar_loja, name='criar_loja'),
    path('loja/ver/', views.ver_loja, name='ver_loja'),
    path('loja/excluir/', views.excluir_loja, name='excluir_loja'),
]