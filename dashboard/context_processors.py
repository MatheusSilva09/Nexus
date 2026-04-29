from .models import Loja, Vendedor

def dados_loja(request):
    if request.user.is_authenticated:
        try:
            # 1. Primeiro encontramos o perfil de Vendedor do usuário logado
            vendedor_perfil = Vendedor.objects.filter(usuario=request.user).first()
            
            if vendedor_perfil:
                # 2. Agora buscamos a loja usando o perfil do vendedor
                loja = Loja.objects.filter(vendedor=vendedor_perfil).first()
                return {'loja': loja}
        except Exception:
            return {'loja': None}
            
    return {'loja': None}