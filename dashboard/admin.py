from django.contrib import admin
from .models import Vendedor, Loja, Cliente, Categoria, Produto, Pedido

# Registrando as tabelas para aparecerem no painel

admin.site.register(Cliente)
admin.site.register(Categoria)
admin.site.register(Produto)
admin.site.register(Pedido)

@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'aprovado', 'data_cadastro')
    list_filter = ('aprovado', 'data_cadastro')
    search_fields = ('usuario__username', 'usuario__email')
    ordering = ('-data_cadastro',)
    actions = ['aprovar_vendedores']

    @admin.action(description="Aprovar vendedores selecionados")
    def aprovar_vendedores(self, request, queryset):
        quantidade = queryset.update(aprovado=True)
        self.message_user(request, f"{quantidade} vendedores foram aprovados com sucesso.")

@admin.register(Loja)
class LojaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'vendedor')
    search_fields = ('nome', 'vendedor__usuario__username')