# 1. Ferramentas do Django
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction

# 2. Seus modelos (as tabelas do Nexus)
from .models import Produto, Pedido, ItemPedido, Carrinho
def finalizar_pedido(request):
    # 1. Pegamos o carrinho do usuário (supondo que ele esteja logado)
    carrinho = Carrinho.objects.get(usuario=request.user)
    itens_carrinho = carrinho.itens.all() # Relacionamento com ItemCarrinho

    if not itens_carrinho:
        return render(request, 'erro.html', {'msg': 'Seu carrinho está vazio!'})

    # 2. Iniciamos uma transação atômica
    try:
        with transaction.atomic():
            # Criamos o Pedido inicial (Status: Aguardando)
            novo_pedido = Pedido.objects.create(
                cliente=request.user.cliente,
                total=0,  # Vamos calcular abaixo
                status='Aguardando Pagamento'
            )

            valor_total = 0

            # 3. Processamos item por item
            for item in itens_carrinho:
                produto = item.produto

                # Validação Crítica de Estoque
                if produto.estoque < item.quantidade:
                    # Se um único item falhar, a transação inteira é cancelada
                    raise ValueError(f"Estoque insuficiente para {produto.nome}")

                # Criamos o Item do Pedido (o histórico da venda)
                ItemPedido.objects.create(
                    pedido=novo_pedido,
                    produto=produto,
                    quantidade=item.quantidade,
                    preco_unitario=produto.preco
                )

                # Atualizamos o estoque do produto
                produto.estoque -= item.quantidade
                produto.save()

                # Somamos ao total
                valor_total += (produto.preco * item.quantidade)

            # 4. Atualizamos o valor final do pedido e limpamos o carrinho
            novo_pedido.total = valor_total
            novo_pedido.save()
            
            itens_carrinho.delete() # Carrinho vazio após a compra

        return render(request, 'sucesso.html', {'pedido': novo_pedido})

    except ValueError as e:
        # Se cair aqui, o banco de dados não sofreu NENHUMA alteração
        return render(request, 'erro.html', {'msg': str(e)})
    
@login_required
def atualizar_quantidade_estoque(request, produto_id):
    if request.method == "POST":
        produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
        nova_quantidade = request.POST.get('quantidade')
        operacao = request.POST.get('operacao') # 'adicionar' ou 'substituir'

        if operacao == 'adicionar':
            produto.estoque += int(nova_quantidade)
        else:
            produto.estoque = int(nova_quantidade)
            
        produto.save()
        return redirect('estoque_lista')
    
@login_required
def lista_estoque(request):
    # 1. Começamos pegando todos os produtos da loja do vendedor logado
    produtos = Produto.objects.filter(loja__vendedor__usuario=request.user)

    # 2. Filtro de Busca por Nome (se o vendedor digitar algo na busca)
    nome_filtro = request.GET.get('nome')
    if nome_filtro:
        produtos = produtos.filter(nome__icontains=nome_filtro)

    # 3. Filtro de Estoque Baixo (se o vendedor marcar a opção)
    estoque_baixo = request.GET.get('baixo_estoque')
    if estoque_baixo:
        # Filtra produtos onde estoque é menor ou igual a 5 (ou seu estoque_minimo)
        produtos = produtos.filter(estoque__lte=5) 

    return render(request, 'estoque_lista.html', {'produtos': produtos})

@login_required
def home(request):
    return render(request, "dashboard.html")

@login_required
def profile(request):
    # Por enquanto, apenas renderiza uma página de perfil (que você pode criar depois)
    return render(request, "dashboard/profile.html")

@login_required
def adicionar_produto(request):
    if request.method == 'POST':
        # Capturando os dados enviados pelo name do input no HTML
        nome = request.POST.get('nome')
        preco = request.POST.get('preco')
        estoque = request.POST.get('estoque')
        estoque_minimo = request.POST.get('estoque_minimo')

        # Criando o objeto Produto manualmente no banco
        # Usamos .vendedor.loja para garantir que o produto vá para a loja certa
        Produto.objects.create(
            nome=nome,
            preco=preco,
            estoque=estoque,
            estoque_minimo=estoque_minimo,
            loja=request.user.vendedor.loja 
        )
        
        return redirect('lista_estoque')

    return render(request, 'produto_form.html')

@login_required
def excluir_produto(request, produto_id):
    # Buscamos o produto garantindo que ele pertence ao usuário logado (segurança!)
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    produto.delete()
    return redirect('lista_estoque')

@login_required
def editar_produto(request, produto_id):
    # 1. Busca o produto original no banco
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)

    if request.method == 'POST':
        # 2. Captura os novos dados do formulário
        produto.nome = request.POST.get('nome')
        produto.preco = request.POST.get('preco')
        produto.estoque = request.POST.get('estoque')
        produto.estoque_minimo = request.POST.get('estoque_minimo')
        
        # 3. Salva as alterações
        produto.save()
        return redirect('lista_estoque')

    # 4. Se for GET, envia o produto para o formulário já vir preenchido
    return render(request, 'produto_editar.html', {'produto': produto})

@login_required
def realizar_venda(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    
    if request.method == 'POST':
        quantidade_vendida = int(request.POST.get('quantidade', 1))
        
        if produto.estoque >= quantidade_vendida:
            produto.estoque -= quantidade_vendida
            produto.save()
            # Aqui poderíamos criar um objeto "Venda" para o relatório depois
            return redirect('lista_estoque')
        else:
            # Caso o vendedor tente vender mais do que tem
            erro = "Estoque insuficiente!"
            return render(request, 'venda_form.html', {'produto': produto, 'erro': erro})

    return render(request, 'venda_form.html', {'produto': produto})

from django.db.models import Sum, F

@login_required
def home(request):
    # Pega apenas os produtos da loja do usuário logado
    produtos_loja = Produto.objects.filter(loja__vendedor__usuario=request.user)

    # 1. Valor Total em Estoque (Soma de Preço * Quantidade de cada item)
    # Usamos aggregate para fazer o cálculo direto no banco de dados (mais rápido)
    total_estoque = produtos_loja.aggregate(
        total=Sum(F('preco') * F('estoque'))
    )['total'] or 0

    # 2. Itens com Estoque Baixo (Avisos)
    avisos = produtos_loja.filter(estoque__lte=F('estoque_minimo')).count()

    # 3. Quantidade total de itens cadastrados
    total_itens = produtos_loja.count()

    context = {
        'receita': total_estoque, # Valor patrimonial em estoque
        'vendas': total_itens,    # Quantidade de SKUs diferentes
        'avisos': avisos,
        'produtos': produtos_loja[:5], # Pega os 5 primeiros para a lista lateral
    }

    return render(request, 'dashboard.html', context)