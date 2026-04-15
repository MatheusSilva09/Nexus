from django.contrib import admin
from .models import Vendedor, Loja, Cliente, Categoria, Produto, Pedido

# Registrando as tabelas para aparecerem no painel
admin.site.register(Vendedor)
admin.site.register(Loja)
admin.site.register(Cliente)
admin.site.register(Categoria)
admin.site.register(Produto)
admin.site.register(Pedido)