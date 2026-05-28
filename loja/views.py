from django.shortcuts import render, redirect, get_object_or_404
from dashboard.models import Produto 
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import transaction
from dashboard.models import Produto, Pedido, ItemPedido, Cliente, Loja

# 1. VIEW DA VITRINE (Já está funcionando!)
def vitrine_view(request):
    # Opção A: Exibir produtos de TODAS as lojas cadastradas
    produtos = Produto.objects.filter(estoque__gt=0)
    
    # Opção B (Mais profissional): Filtrar por uma loja específica se o usuário escolher
    loja_id = request.GET.get('loja_id')
    if loja_id:
        produtos = produtos.filter(loja_id=loja_id)
        
    carrinho = request.session.get('carrinho', {})
    total_itens = sum(carrinho.values())
    
    context = {
        'titulo_aba': 'NEXUS Store | Gestão Modular Inteligente',
        'produtos': produtos,
        'lojas': Loja.objects.all(), # Para criar um menu de seleção de lojas
        'total_itens': total_itens,
    }
    return render(request, 'vitrine.html', context)

# 2. VIEW PARA ADICIONAR ITEM AO CARRINHO
def adicionar_ao_carrinho_view(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)
    
    # Obtém o carrinho da sessão atual (se não existir, cria um dicionário vazio)
    carrinho = request.session.get('carrinho', {})
    
    # Converte o ID para string porque as chaves da sessão em JSON precisam ser strings
    prod_id_str = str(produto_id)
    
    # Se o produto já está no carrinho e ainda tem estoque disponível, aumenta a quantidade
    if prod_id_str in carrinho:
        if produto.estoque > carrinho[prod_id_str]:
            carrinho[prod_id_str] += 1
    else:
        carrinho[prod_id_str] = 1
        
    # Salva o carrinho atualizado de volta na sessão
    request.session['carrinho'] = carrinho
    # Avisa ao Django que a sessão foi modificada para ele gravar no banco/cookie
    request.session.modified = True
    
    return redirect('vitrine')


# 3. VIEW PARA VISUALIZAR O CARRINHO
def ver_carrinho_view(request):
    carrinho = request.session.get('carrinho', {})
    itens_carrinho = []
    valor_total = 0
    
    # Varremos o dicionário da sessão para montar os dados reais do banco
    for prod_id, quantidade in carrinho.items():
        try:
            produto = Produto.objects.get(id=int(prod_id))
            subtotal = produto.preco * quantidade
            valor_total += subtotal
            
            itens_carrinho.append({
                'produto': produto,
                'quantidade': quantidade,
                'subtotal': subtotal
            })
        except Produto.DoesNotExist:
            continue
            
    total_itens = sum(carrinho.values())
            
    context = {
        'titulo_aba': 'NEXUS Store | Gestão Modular Inteligente',
        'itens_carrinho': itens_carrinho,
        'valor_total': valor_total,
        'total_itens': total_itens,
    }
    return render(request, 'carrinho.html', context)

# 4. VIEW PARA REMOVER UM ITEM OU DIMINUIR QUANTIDADE
def remover_do_carrinho_view(request, produto_id):
    carrinho = request.session.get('carrinho', {})
    prod_id_str = str(produto_id)
    
    if prod_id_str in carrinho:
        if carrinho[prod_id_str] > 1:
            carrinho[prod_id_str] -= 1 # Diminui uma unidade
        else:
            del carrinho[prod_id_str] # Remove o produto por completo se for a última unidade
            
    request.session['carrinho'] = carrinho
    request.session.modified = True
    return redirect('ver_carrinho')


# 5. VIEW PARA FINALIZAR O PEDIDO GRAVANDO NO BANCO DE DADOS
@login_required(login_url='loja_login') # Se não estiver logado, joga para a tela de login da loja
def finalizar_pedido_view(request):
    carrinho = request.session.get('carrinho', {})
    
    if not carrinho:
        messages.warning(request, "Seu carrinho está vazio.")
        return redirect('vitrine')
        
    cliente, created = Cliente.objects.get_or_create(
        usuario=request.user,
        defaults={
            'nome': request.user.get_full_name() or request.user.username,
            'email': request.user.email
        }
    )
    
    itens_para_processar = []
    valor_total_pedido = 0
    
    # Validação rigorosa de estoque antes de abrir a transação
    for prod_id, quantidade in carrinho.items():
        try:
            produto = Produto.objects.get(id=int(prod_id))
            
            if produto.estoque < quantidade:
                messages.error(request, f"Estoque insuficiente para {produto.nome}. Disponível: {produto.estoque}.")
                return redirect('ver_carrinho')
                
            subtotal = produto.preco * quantidade
            valor_total_pedido += subtotal
            itens_para_processar.append((produto, quantidade, produto.preco))
            
        except Produto.DoesNotExist:
            messages.error(request, "Produto não encontrado.")
            return redirect('ver_carrinho')

    # Gravação atômica no banco de dados
    try:
        with transaction.atomic():
            # 1. Cria o Pedido
            pedido = Pedido.objects.create(
                cliente=cliente,
                total=valor_total_pedido,
                status='Aguardando Pagamento',
                pago=False
            )
            
            # 2. Cria os itens e deduz do estoque usando o método do seu model
            for produto, quantidade, preco in itens_para_processar:
                ItemPedido.objects.create(
                    pedido=pedido,
                    produto=produto,
                    preco=preco,
                    quantidade=quantidade
                )
                
                # Executa a função do seu models.py que salva a redução no banco!
                produto.diminuir_estoque(quantidade)
                
            # 3. Limpa a sessão
            request.session['carrinho'] = {}
            request.session.modified = True
            
            messages.success(request, f"Pedido #{pedido.id} realizado com sucesso!")
            return redirect('loja_meus_pedidos')
            
    except Exception as e:
        messages.error(request, f"Erro no checkout: {str(e)}")
        return redirect('ver_carrinho')

# 6. VIEW DE LOGIN DO CLIENTE
def loja_login_view(request):
    if request.method == 'POST':
        usuario_form = request.POST.get('username')
        senha_form = request.POST.get('password')
        
        user = authenticate(request, username=usuario_form, password=senha_form)
        
        if user is not None:
            login(request, user)
            # Se for alguém da equipe do painel, podemos mandar pro dashboard, senão fica na loja
            if user.is_staff:
                return redirect('home')
            return redirect('vitrine')
        else:
            messages.error(request, "Usuário ou senha incorretos.")
            
    return render(request, 'loja_login.html')

# 7. VIEW DE CADASTRO DO CLIENTE
def loja_cadastro_view(request):
    if request.method == 'POST':
        usuario_form = request.POST.get('username')
        email_form = request.POST.get('email')
        senha_form = request.POST.get('password')
        confirma_senha = request.POST.get('password_confirm')
        
        if User.objects.filter(username=usuario_form).exists():
            return render(request, 'loja_cadastro.html', {'error': 'Este nome de usuário já está em uso.'})
            
        if senha_form != confirma_senha:
            return render(request, 'loja_cadastro.html', {'error': 'As senhas não coincidem.'})
            
        # Cria o usuário como cliente comum (is_staff=False por padrão)
        user = User.objects.create_user(username=usuario_form, email=email_form, password=senha_form)
        login(request, user)
        return redirect('vitrine')
        
    return render(request, 'loja_cadastro.html')

# 8. VIEW DE LOGOUT DA LOJA
def loja_logout_view(request):
    logout(request)
    return redirect('vitrine')

# 9. VIEW DO HISTÓRICO DE PEDIDOS DO CLIENTE
@login_required(login_url='loja_login')
def loja_meus_pedidos_view(request):
    # Obtém o cliente do usuário logado
    try:
        cliente = Cliente.objects.get(usuario=request.user)
        # Busca todos os pedidos dele ordenados pelo id mais recente
        pedidos = Pedido.objects.filter(cliente=cliente).order_by('-id')
    except Cliente.DoesNotExist:
        pedidos = []
        
    carrinho = request.session.get('carrinho', {})
    total_itens = sum(carrinho.values())
        
    context = {
        'titulo_aba': 'NEXUS Store | Gestão Modular Inteligente',
        'pedidos': pedidos,
        'total_itens': total_itens,
    }
    return render(request, 'loja_meus_pedidos.html', context)

# 10. VIEW DE DETALHES DO PRODUTO
def detalhe_produto_loja_view(request, produto_id):
    # Busca o produto ou retorna 404 se não existir
    produto = get_object_or_404(Produto, id=produto_id)
    
    # Busca todas as imagens extras cadastradas na galeria deste produto (ProdutoImagem)
    galeria = produto.imagens.all() 
    
    carrinho = request.session.get('carrinho', {})
    total_itens = sum(carrinho.values())
    
    context = {
        'produto': produto,
        'galeria': galeria,
        'total_itens': total_itens,
    }
    return render(request, 'detalhe_produto_loja.html', context)