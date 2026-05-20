from django.contrib import admin
from .models import Vendedor, Loja, Cliente, Categoria, Produto, Pedido, Perfil # Não esqueça de importar o Perfil!

# Configurações de exibição do NEXUS Hub Admin
admin.site.site_header = "NEXUS Hub - Administração"
admin.site.site_title = "Portal NEXUS Hub"
admin.site.index_title = "Gerenciamento do Ecossistema NEXUS Hub"

admin.site.register(Cliente)
admin.site.register(Categoria)
admin.site.register(Produto)
admin.site.register(Pedido)

# 1. Registre o Perfil (ESSENCIAL para o Matheus ter uma loja vinculada)
@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'nivel', 'loja')
    list_filter = ('nivel', 'loja')
    search_fields = ('usuario__username', 'loja__nome')

# 2. Mantenha o Vendedor se você ainda o usa, mas cuidado com os conflitos
@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'aprovado', 'data_cadastro')
    # ... resto das suas configurações ...

# 3. Ajuste a Loja (Como o Perfil agora manda na Loja, remova o 'vendedor' daqui se ele estiver dando erro)
@admin.register(Loja)
class LojaAdmin(admin.ModelAdmin):
    list_display = ('nome',) 
    search_fields = ('nome',)