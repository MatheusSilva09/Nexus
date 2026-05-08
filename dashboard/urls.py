from django.urls import path
from dashboard import views
from . import views

urlpatterns = [
    # --- Rota da Home/Dashboard ---
    path('', views.dashboard_view, name='home'),
    path('', views.dashboard_view, name='dashboard'),
    
    # --- Rotas de Autenticação ---
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # --- Rotas de Clientes ---
    # Esta é a lista que você chama após salvar
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/novo/', views.cadastrar_cliente, name='cadastrar_cliente'),
    path('clientes/editar/<int:pk>/', views.editar_cliente, name='editar_cliente'),
    path('clientes/excluir/<int:pk>/', views.excluir_cliente, name='excluir_cliente'),

    # --- Rotas de Estoque/Produtos ---
    path('vitrine/', views.vitrine_produtos, name='vitrine_produtos'),
    path('carrinho/adicionar/<int:produto_id>/', views.adicionar_ao_carrinho, name='adicionar_ao_carrinho'),
    path('carrinho/', views.ver_carrinho, name='ver_carrinho'),
    path('carrinho/remover/<int:produto_id>/', views.remover_do_carrinho, name='remover_do_carrinho'),
    path('pedido/<int:pedido_id>/', views.detalhe_pedido, name='detalhe_pedido'),
    path('meus-pedidos/', views.historico_pedidos, name='historico_pedidos'),
    path('estoque/novo/', views.cadastrar_produto, name='cadastrar_produto'),
    path('estoque/', views.lista_estoque, name='lista_estoque'),
    path('estoque/detalhe/<int:produto_id>/', views.detalhe_produto, name='detalhe_produto'),
    path('estoque/editar/<int:produto_id>/', views.editar_produto, name='editar_produto'),
    path('estoque/excluir/<int:produto_id>/', views.excluir_produto, name='excluir_produto'),
    path('estoque/vender/<int:produto_id>/', views.realizar_venda, name='realizar_venda'),
    path('cadastrar-categoria/', views.cadastrar_categoria, name='cadastrar_categoria'),
    
    # --- Rotas de Loja ---
    path('excluir_loja/', views.excluir_loja, name='excluir_loja'),
    path('funcionarios/', views.lista_funcionarios, name='lista_funcionarios'),
    path('funcionarios/novo/', views.adicionar_funcionario, name='adicionar_funcionario'),
    path('funcionarios/editar/<int:id>/', views.editar_funcionario, name='editar_funcionario'),
    path('funcionarios/excluir/<int:id>/', views.excluir_funcionario, name='excluir_funcionario'),
    

]