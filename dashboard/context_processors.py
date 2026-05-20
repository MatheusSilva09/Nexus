from .models import Loja, Vendedor, Perfil

def dados_loja(request):
    if request.user.is_authenticated:
        try:
            # 1. Primeiro encontramos o perfil de Vendedor do usuário logado
            vendedor_perfil = Vendedor.objects.filter(usuario=request.user).first()
            
            # 2. Verifica se é um vendedor aprovado (não admin)
            is_vendedor = vendedor_perfil and vendedor_perfil.aprovado and not request.user.is_superuser
            
            # 3. Verifica se é um cliente
            perfil = Perfil.objects.filter(usuario=request.user).first()
            is_cliente = perfil.nivel == 'CLIENTE' if perfil else False

            if vendedor_perfil:
                # 4. Agora buscamos a loja usando o perfil do vendedor
                loja = Loja.objects.filter(vendedor=vendedor_perfil).first()
                return {
                    'loja': loja,
                    'is_vendedor': is_vendedor,
                    'is_cliente': is_cliente,
                    'is_admin': request.user.is_superuser,
                }
        except Exception:
            return {
                'loja': None,
                'is_vendedor': False,
                'is_cliente': False,
                'is_admin': request.user.is_superuser,
            }
            
    return {
        'loja': None,
        'is_vendedor': False,
        'is_cliente': False,
        'is_admin': request.user.is_superuser,
    }