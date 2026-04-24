from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, F
from django.contrib.auth.decorators import user_passes_test
from .models import Cliente, Loja, Produto, Pedido, ItemPedido, Carrinho
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages

# --- DASHBOARD ---

@login_required
def home(request):
    perfil = request.user.perfil

    
    
    # Lógica de autoridade: O Hub vê tudo, o Vendedor vê sua loja
    if perfil.nivel == 'ADMIN':
        produtos_loja = Produto.objects.all()  # Acesso total
    else:
        # Garante que o vendedor veja apenas sua própria loja
        produtos_loja = Produto.objects.filter(loja=perfil.loja)

    # Cálculo das métricas (funciona para ambos, com filtros diferentes)
    total_estoque = produtos_loja.aggregate(total=Sum(F('preco') * F('estoque')))['total'] or 0
    avisos = produtos_loja.filter(estoque__lte=F('estoque_minimo')).count()
    
    context = {
        'receita': total_estoque,
        'vendas': produtos_loja.count(),
        'avisos': avisos,
        'produtos': produtos_loja[:5],
        'nivel': perfil.nivel, # Útil para exibir elementos diferentes no HTML (ex: botão de 'Gestão Global')
    }
    if not hasattr(request.user, 'perfil'):
        # Opção: criar um perfil padrão automaticamente ou avisar o usuário
        return render(request, 'erro.html', {'msg': 'Seu usuário não possui um perfil configurado.'})
    
    perfil = request.user.perfil
    return render(request, 'dashboard.html', context)

@login_required
def profile(request):
    return render(request, "profile.html")

def login_view(request):
    if request.method == 'POST':
        user_nome = request.POST.get('username')
        senha = request.POST.get('password')
        
        user = authenticate(request, username=user_nome, password=senha)
        
        if user is not None:
            login(request, user)
            # Redireciona para home, onde já temos a lógica de Perfil
            return redirect('home')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')
            
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login_view')

# --- ESTOQUE E PRODUTOS ---

@login_required
def lista_estoque(request):
    produtos = Produto.objects.filter(loja__vendedor__usuario=request.user)
    nome_filtro = request.GET.get('nome')
    if nome_filtro:
        produtos = produtos.filter(nome__icontains=nome_filtro)
    if request.GET.get('baixo_estoque'):
        produtos = produtos.filter(estoque__lte=F('estoque_minimo'))
    return render(request, 'estoque_lista.html', {'produtos': produtos})

@login_required
def adicionar_produto(request):
    if request.method == 'POST':
        Produto.objects.create(
            nome=request.POST.get('nome'),
            preco=request.POST.get('preco'),
            estoque=request.POST.get('estoque'),
            estoque_minimo=request.POST.get('estoque_minimo'),
            loja=request.user.vendedor.loja 
        )
        return redirect('lista_estoque')
    return render(request, 'produto_form.html')

@login_required
def editar_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    if request.method == 'POST':
        produto.nome = request.POST.get('nome')
        produto.preco = request.POST.get('preco')
        produto.estoque = request.POST.get('estoque')
        produto.estoque_minimo = request.POST.get('estoque_minimo')
        produto.save()
        return redirect('lista_estoque')
    return render(request, 'produto_editar.html', {'produto': produto})

@login_required
def excluir_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    produto.delete()
    return redirect('lista_estoque')

@login_required
def atualizar_quantidade_estoque(request, produto_id):
    if request.method == "POST":
        produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
        nova_quantidade = int(request.POST.get('quantidade', 0))
        operacao = request.POST.get('operacao')
        if operacao == 'adicionar':
            produto.estoque += nova_quantidade
        else:
            produto.estoque = nova_quantidade
        produto.save()
        return redirect('lista_estoque')
    return redirect('lista_estoque')

# --- VENDAS E CLIENTES ---

@login_required
def finalizar_pedido(request):
    carrinho = Carrinho.objects.get(cliente__usuario=request.user)
    itens_carrinho = carrinho.itens.all()
    if not itens_carrinho:
        return render(request, 'erro.html', {'msg': 'Seu carrinho está vazio!'})
    try:
        with transaction.atomic():
            novo_pedido = Pedido.objects.create(
                cliente=request.user.cliente,
                total=0,
                status='Aguardando Pagamento'
            )
            valor_total = 0
            for item in itens_carrinho:
                produto = item.produto
                if produto.estoque < item.quantidade:
                    raise ValueError(f"Estoque insuficiente para {produto.nome}")
                ItemPedido.objects.create(
                    pedido=novo_pedido,
                    produto=produto,
                    quantidade=item.quantidade,
                    preco=produto.preco
                )
                produto.estoque -= item.quantidade
                produto.save()
                valor_total += (produto.preco * item.quantidade)
            novo_pedido.total = valor_total
            novo_pedido.save()
            itens_carrinho.delete()
        return render(request, 'sucesso.html', {'pedido': novo_pedido})
    except ValueError as e:
        return render(request, 'erro.html', {'msg': str(e)})

@login_required
def realizar_venda(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    if request.method == 'POST':
        quantidade = int(request.POST.get('quantidade', 1))
        if produto.estoque >= quantidade:
            produto.estoque -= quantidade
            produto.save()
            return redirect('lista_estoque')
        return render(request, 'venda_form.html', {'produto': produto, 'erro': "Estoque insuficiente!"})
    return render(request, 'venda_form.html', {'produto': produto})

@login_required
def lista_clientes(request):
    clientes = Cliente.objects.filter(loja__vendedor__usuario=request.user)
    return render(request, 'lista_clientes.html', {'clientes': clientes})

@login_required
def adicionar_cliente(request):
    if request.method == 'POST':
        Cliente.objects.create(
            loja=request.user.vendedor.loja,
            nome=request.POST.get('nome'),
            telefone=request.POST.get('telefone', ''),
            endereco=request.POST.get('endereco', '')
        )
        return redirect('lista_clientes')
    return render(request, 'cliente_form.html')

def is_nexus_hub(user):
    return user.is_superuser or user.perfil.nivel == 'ADMIN'

@user_passes_test(is_nexus_hub)
def relatorio_global(request):
    perfil = request.user.perfil
    if perfil.nivel != 'ADMIN':
        return redirect('home')