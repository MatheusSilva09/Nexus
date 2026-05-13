from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Loja, Vendedor

def loja_obrigatoria(view_func):
    @login_required(login_url='login_view')
    def _wrapped_view(request, *args, **kwargs):
        # 1. Se for administrador (superuser), o acesso é livre
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        # 2. Verifica se o usuário tem um perfil de vendedor e uma loja
        vendedor = Vendedor.objects.filter(usuario=request.user).first()
        tem_loja = Loja.objects.filter(vendedor=vendedor).exists() if vendedor else False

        if tem_loja:
            return view_func(request, *args, **kwargs)
        
        # 3. Caso não tenha loja e não seja admin, bloqueia e avisa
        messages.warning(request, "Você precisa configurar uma loja antes de acessar o estoque ou clientes.")
        return redirect('criar_loja')

    return _wrapped_view

def vendedor_aprovado_required(view_func):
    @login_required(login_url='login_view')
    def _wrapped_view(request, *args, **kwargs):
        # Admins sempre passam
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
            
        vendedor = getattr(request.user, 'vendedor', None)
        
        if vendedor and vendedor.aprovado:
            return view_func(request, *args, **kwargs)
        
        messages.error(request, "Seu cadastro de vendedor ainda aguarda aprovação de um administrador.")
        return redirect('login') # Ou uma página de "Aguarde Aprovação"
        
    return _wrapped_view

def vendedor_restrito_required(view_func):
    """
    Decorador para restringir acesso apenas às abas permitidas para Vendedores aprovados.
    Vendedores podem acessar: Estoque e Loja (Criar Loja)
    """
    @login_required(login_url='login_view')
    def _wrapped_view(request, *args, **kwargs):
        # Admins e superusers têm acesso total
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Verifica se o usuário é um vendedor aprovado
        vendedor = Vendedor.objects.filter(usuario=request.user).first()
        
        if not vendedor or not vendedor.aprovado:
            messages.error(request, "Acesso negado. Apenas vendedores aprovados podem acessar.")
            return redirect('login')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

def admin_only_required(view_func):
    """
    Decorador para bloquear acesso de vendedores às funcionalidades administrativas.
    Apenas superusers podem acessar.
    """
    @login_required(login_url='login_view')
    def _wrapped_view(request, *args, **kwargs):
        # Apenas superusers têm acesso
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Vendedores são bloqueados
        vendedor = Vendedor.objects.filter(usuario=request.user).first()
        if vendedor and vendedor.aprovado:
            messages.error(request, "Acesso negado. Esta funcionalidade é exclusiva do administrador.")
            return redirect('lista_estoque')
        
        messages.error(request, "Acesso negado.")
        return redirect('login')
    
    return _wrapped_view