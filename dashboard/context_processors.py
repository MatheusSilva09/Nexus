from .models import Loja, Vendedor, Perfil

def dados_loja(request):
    if request.user.is_authenticated:
        try:
            # 1. Primeiro encontramos o perfil de Vendedor do usuário logado
            vendedor_perfil = Vendedor.objects.filter(usuario=request.user).first()
            
            # 2. Verifica se é um vendedor aprovado (não admin)
            is_vendedor = vendedor_perfil and vendedor_perfil.aprovado and not request.user.is_superuser # Vendedor aprovado que NÃO é superuser
            
            # 3. Verifica o nível do perfil e se é cliente
            perfil = Perfil.objects.filter(usuario=request.user).first()
            is_cliente = perfil and perfil.nivel == 'CLIENTE' and not request.user.is_superuser # Cliente que NÃO é superuser

            if vendedor_perfil:
                # 4. Agora buscamos a loja usando o perfil do vendedor
                loja = Loja.objects.filter(vendedor=vendedor_perfil).first()
                return {
                    'loja': loja,
                    'is_vendedor': is_vendedor,
                    'is_cliente': is_cliente,
                    'is_admin': request.user.is_superuser or (perfil and perfil.nivel == 'ADMIN'), # Superuser OU perfil ADMIN
                    'perfil': perfil, # Passa o objeto perfil para acesso ao .nivel no template
                }
        except Exception:
            return {
                'loja': None,
                'is_vendedor': False,
                'is_cliente': False,
                'is_admin': request.user.is_superuser, # Fallback para is_admin
                'perfil': None,
            }
            
    return {
        'loja': None,
        'is_vendedor': False,
        'is_cliente': False,
        'is_admin': False, # Default para não autenticados
        'perfil': None,
    }