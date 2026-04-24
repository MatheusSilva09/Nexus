from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, F
from django.contrib.auth.decorators import user_passes_test
from .models import Cliente, Loja, Produto, Pedido, ItemPedido, Carrinho, Vendedor
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
    # 1. Verifica se a loja existe ANTES de qualquer processamento
    try:
        loja = request.user.vendedor.loja
    except (Vendedor.DoesNotExist, AttributeError, Loja.DoesNotExist):
        return render(request, 'erro.html', {'msg': 'Você precisa criar uma loja antes de cadastrar produtos!'})

    # 2. Processa o POST apenas uma vez
    if request.method == 'POST':
        Produto.objects.create(
            loja=loja, # Usamos a loja recuperada acima
            nome=request.POST.get('nome'),
            preco=request.POST.get('preco'),
            estoque=request.POST.get('estoque'),
            estoque_minimo=request.POST.get('estoque_minimo')
        )

@login_required
def adicionar_produto(request):
    try:
        loja = request.user.vendedor.loja
    except (Vendedor.DoesNotExist, AttributeError, Loja.DoesNotExist):
        return render(request, 'erro.html', {'msg': 'Você precisa criar uma loja antes de cadastrar produtos!'})
    
    if request.method == 'POST':
        # Usamos o or '0' para garantir que, se vier vazio, ele salve como 0
        estoque = request.POST.get('estoque') or '0'
        estoque_minimo = request.POST.get('estoque_minimo') or '0'
        
        Produto.objects.create(
            loja=loja,
            nome=request.POST.get('nome'),
            preco=request.POST.get('preco') or '0.0',
            estoque=estoque,
            estoque_minimo=estoque_minimo
        )
        return redirect('lista_estoque')
    
    return render(request, 'produto_form.html')

    return redirect('lista_estoque') # Redireciona para a sua lista de produtos


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

from django.shortcuts import render, redirect, get_object_or_404
from .models import Cliente # Certifique-se de importar o modelo de Cliente

@login_required
def editar_cliente(request, cliente_id):
    # Busca o cliente ou retorna 404 se não existir
    cliente = get_object_or_404(Cliente, id=cliente_id)
    
    if request.method == 'POST':
        # Atualiza os dados vindo do formulário
        cliente.nome = request.POST.get('nome')
        cliente.email = request.POST.get('email')
        cliente.telefone = request.POST.get('telefone')
        cliente.save()
        return redirect('lista_clientes')
        
    # Se for GET, renderiza o formulário (pode ser o mesmo 'cliente_form.html' que você usa para criar)
    return render(request, 'cliente_form.html', {'cliente': cliente})

@login_required
def excluir_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    
    if request.method == 'POST':
        cliente.delete()
        return redirect('lista_clientes')
        
    # Exibe uma página de confirmação antes de deletar
    return render(request, 'excluir_cliente_confirmar.html', {'cliente': cliente})

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
    
# --- LOJA ---

@login_required
def criar_loja(request):
    vendedor, created = Vendedor.objects.get_or_create(usuario=request.user)
    
    # Verifica se já existe uma loja para esse vendedor
    loja_existente = Loja.objects.filter(vendedor=vendedor).first()

    if request.method == 'POST':
        if loja_existente:
            # Se já existe, apenas atualiza os dados existentes
            loja_existente.nome = request.POST.get('nome')
            loja_existente.descricao = request.POST.get('descricao')
            loja_existente.save()
            return redirect('home')
        else:
            # Se não existe, cria a nova
            Loja.objects.create(
                vendedor=vendedor,
                nome=request.POST.get('nome'),
                descricao=request.POST.get('descricao')
            )
            telefone_limpo = request.POST.get('telefone').replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
        vendedor.telefone = telefone_limpo
        vendedor.save()
        return redirect('home')

    # No GET, se a loja existir, você pode passar ela para o template para pré-preencher
    return render(request, 'criar_loja.html', {'loja': loja_existente})
    
    if request.method == 'POST':
        # 1. Captura os dados do formulário
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao')
        telefone = request.POST.get('telefone')
        
        # 2. Garante que o usuário logado tenha um registro de 'Vendedor'
        # O get_or_create evita erros caso o registro ainda não exista
        vendedor, created = Vendedor.objects.get_or_create(usuario=request.user)
        
        # Se você quiser atualizar o telefone no registro de vendedor
        if vendedor.telefone != telefone:
            vendedor.telefone = telefone
            vendedor.save()
        
        # 3. Cria a Loja vinculada ao Vendedor
        Loja.objects.create(
            vendedor=vendedor,
            nome=nome,
            descricao=descricao
        )
        
        # 4. Redireciona para o dashboard após o sucesso
        return redirect('home')
    
    return render(request, 'criar_loja.html')

def ver_loja(request):
    # Busca a loja do vendedor logado
    loja = Loja.objects.filter(vendedor__usuario=request.user).first()
    if not loja:
        return render(request, 'erro.html', {'msg': 'Você ainda não possui uma loja cadastrada.'})
    return render(request, 'ver_loja.html', {'loja': loja})

@login_required
def excluir_loja(request):
    loja = Loja.objects.filter(vendedor__usuario=request.user).first()
    if request.method == 'POST':
        if loja:
            loja.delete()
        return redirect('home')
    return render(request, 'excluir_loja.html', {'loja': loja})