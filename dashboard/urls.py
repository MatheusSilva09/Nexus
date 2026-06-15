from django.urls import path, include
from django.contrib import admin
from . import views

urlpatterns = [
    # ==========================================
    # 1. ROTAS INTERNAS DO DASHBOARD / GERENCIAMENTO
    # Agrupamos tudo o que é administrativo sob o prefixo 'dashboard/'
    # ==========================================
    path('dashboard/', views.home, name='home'),
    path('dashboard/painel/', views.dashboard_view, name='dashboard'),
    
    # --- Rotas de Autenticação ---
    path('dashboard/logout/', views.logout_view, name='logout_view'),
    path('dashboard/signup/', views.signup_view, name='signup_view'),
    path('dashboard/registrar/', views.signup_view, name='registrar'),

    # --- Rotas de Clientes ---
    path('dashboard/clientes/', views.base_clientes, name='base_clientes'),
    path('dashboard/clientes/novo/', views.cadastrar_cliente, name='cadastrar_cliente'),
    path('dashboard/clientes/editar/<int:pk>/', views.editar_cliente, name='editar_cliente'),
    path('dashboard/clientes/excluir/<int:pk>/', views.excluir_cliente, name='excluir_cliente'),

    # --- Rotas de Estoque/Produtos ---
    path('dashboard/estoque/novo/', views.cadastrar_produto, name='cadastrar_produto'),
    path('dashboard/estoque/', views.lista_estoque, name='lista_estoque'),
    path('dashboard/estoque/detalhe/<int:produto_id>/', views.detalhe_produto, name='detalhe_produto'),
    path('dashboard/estoque/editar/<int:produto_id>/', views.editar_produto, name='editar_produto'),
    path('dashboard/estoque/excluir/<int:produto_id>/', views.excluir_produto, name='excluir_produto'),
    path('dashboard/estoque/vender/<int:produto_id>/', views.realizar_venda, name='realizar_venda'),
    path('dashboard/cadastrar-categoria/', views.cadastrar_categoria, name='cadastrar_categoria'),
    path('dashboard/categorias/editar-ajax/<int:categoria_id>/', views.editar_categoria_ajax, name='editar_categoria_ajax'),
    
    # --- Rotas de Gerenciamento da Loja ---
    path('dashboard/loja/', views.ver_loja, name='ver_loja'),
    path('dashboard/loja/criar/', views.criar_loja, name='criar_loja'),
    path('dashboard/loja/editar/', views.editar_loja, name='editar_loja'),
    path('dashboard/excluir_loja/', views.excluir_loja, name='excluir_loja'),
    path('dashboard/funcionarios/', views.lista_funcionarios, name='lista_funcionarios'),
    path('dashboard/funcionarios/novo/', views.adicionar_funcionario, name='adicionar_funcionario'),
    path('dashboard/funcionarios/editar/<int:id>/', views.editar_funcionario, name='editar_funcionario'),
    path('dashboard/funcionarios/excluir/<int:id>/', views.excluir_funcionario, name='excluir_funcionario'),
    path('dashboard/estoque/produto/imagem/deletar/<int:imagem_id>/', views.deletar_imagem_galeria, name='deletar_imagem_galeria'),
]