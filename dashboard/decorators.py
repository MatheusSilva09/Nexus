from django.shortcuts import redirect
from django.contrib import messages
from .models import Loja, Vendedor

def loja_obrigatoria(view_func):
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