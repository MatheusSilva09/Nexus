from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q

from dashboard.models import Produto, ItemCarrinho, Cliente, Loja, Pedido, ItemPedido
from decimal import Decimal # Essencial para cálculo de preço
from django.conf import settings # Para acessar o EMAIL_HOST_USER
from django.core.mail import send_mail, mail_admins # Para as notificações
from dashboard.cart import Cart # Importe sua classe Cart (ajuste o caminho se necessário)
from dashboard.models import ItemCarrinho


def vitrine_view(request):
    # 1. Base: Exibir produtos com estoque disponível
    produtos = Produto.objects.filter(estoque__gt=0)
    
    # 2. NOVO: Captura o termo digitado na barra de pesquisa
    termo_busca = request.GET.get('q', '').strip()
    if termo_busca:
        # Busca produtos onde o termo esteja no nome OU na descrição
        produtos = produtos.filter(
            Q(nome__icontains=termo_busca) | 
            Q(descricao__icontains=termo_busca)
        ).distinct()
    
    # 3. Filtrar apenas produtos em promoção se o parâmetro 'ofertas' estiver na URL
    apenas_ofertas = request.GET.get('ofertas') == 'true'
    if apenas_ofertas:
        # Mantém o filtro acumulado com a busca textual
        produtos = produtos.filter(em_oferta=True)
    
    # 4. Filtrar por uma loja específica se o usuário escolher no menu
    loja_id = request.GET.get('loja_id')
    if loja_id:
        produtos = produtos.filter(loja_id=loja_id)
        
    # Garante o uso da chave correta usada no seu gerenciamento de sessões ('cart' ou 'carrinho')
    carrinho = request.session.get('cart', request.session.get('carrinho', {}))
    total_itens = sum(item.get('quantidade', 0) for item in carrinho.values())
    
    context = {
        'titulo_aba': 'NEXUS Store | Gestão Modular Inteligente',
        'produtos': produtos,
        'lojas': Loja.objects.all(),
        'total_itens': total_itens,
        'filtrando_ofertas': apenas_ofertas,
        'termo_busca': termo_busca,  # Enviamos de volta ao HTML para controlar o "X"
    }
    return render(request, 'vitrine.html', context)

def adicionar_ao_carrinho_view(request, produto_id):
    cart = Cart(request)
    produto = get_object_or_404(Produto, id=produto_id)
    cart.add(produto_id=produto.id)
    return redirect('ver_carrinho')

def ver_carrinho_view(request):
    carrinho_sessao = request.session.get('cart', {})
    
    itens_carrinho = []
    total_geral = Decimal('0.00')
    total_itens = 0

    for produto_id, dados in carrinho_sessao.items():
        try:
            produto = Produto.objects.get(id=int(produto_id))
            quantidade = int(dados['quantidade'])
            
            # Instancia o objeto para herdar as propriedades do seu Models.py
            item_objeto = ItemCarrinho(produto=produto, quantidade=quantidade)
            
            # Acumula usando a @property subtotal inteligente que você fez no model
            subtotal_item = Decimal(str(item_objeto.subtotal))
            total_geral += subtotal_item
            total_itens += quantidade
            
            # Injeta o preço original multiplicado pela quantidade para usarmos no preço riscado
            item_objeto.preco_original_total = Decimal(str(produto.preco)) * quantidade
            
            itens_carrinho.append(item_objeto)
            
        except (Produto.DoesNotExist, ValueError, KeyError):
            continue

    # Retorna o dicionário com os nomes exatos que o carrinho.html oficial lê!
    return render(request, 'carrinho.html', {
        'itens_carrinho': itens_carrinho,
        'valor_total': total_geral,  # Antes era total_do_carrinho_nexus
        'total_itens': total_itens
    })

def remover_do_carrinho_view(request, produto_id):
    cart = Cart(request)
    cart.remove(produto_id)
    return redirect('ver_carrinho')

# --- FINALIZAÇÃO DO PEDIDO ---

@transaction.atomic
@login_required
def finalizar_pedido_view(request):
    cart = Cart(request)
    if not cart.cart:
        return redirect('vitrine')

    cliente = Cliente.objects.filter(usuario=request.user).first()
    if not cliente:
        messages.warning(request, "Por favor, complete seus dados de entrega antes de finalizar a compra.")
        return redirect('cadastrar_cliente')

    # 1. Busca todos os produtos ativos do carrinho convertendo IDs para int
    ids_produtos = [int(p_id) for p_id in cart.cart.keys()]
    produtos_dict = {p.id: p for p in Produto.objects.filter(id__in=ids_produtos)}

    total_geral = Decimal('0.00')
    itens_validos_para_criar = []

    # 2. Primeiro loop: validação e cálculo do total seguro
    for p_id, item in cart.cart.items():
        id_int = int(p_id)
        
        # BLINDAGEM CONTRA KEYERROR: Se o produto não existir no banco, pula ele com segurança
        if id_int not in produtos_dict:
            continue
            
        produto = produtos_dict[id_int]
        
        if produto.em_oferta and produto.preco_promocional:
            preco_final = Decimal(str(produto.preco_promocional))
        else:
            preco_final = Decimal(str(produto.preco))
            
        qtd = int(item.get('quantity', item.get('quantidade', 1)))
        total_geral += preco_final * qtd
        
        # Guarda os dados processados para salvar no banco logo abaixo
        itens_validos_para_criar.append({
            'produto': produto,
            'preco_historico': preco_final,
            'quantidade': qtd
        })
    
    # Se por algum motivo nenhum produto do carrinho era válido mais no banco, aborta
    if not itens_validos_para_criar:
        request.session['cart'] = {}
        request.session['carrinho'] = {}
        request.session.modified = True
        messages.error(request, "Os produtos do seu carrinho não estão mais disponíveis no estoque.")
        return redirect('vitrine')

    # Cria o Pedido com o total recalculado apenas das mercadorias reais
    pedido = Pedido.objects.create(cliente=cliente, total=total_geral)

    # 3. Segundo loop: Salva os itens e atualiza os estoques reais
    for item_validificado in itens_validos_para_criar:
        prod = item_validificado['produto']
        qtd_item = item_validificado['quantidade']

        ItemPedido.objects.create(
            pedido=pedido,
            produto=prod,
            preco=item_validificado['preco_historico'],
            quantidade=qtd_item
        )

        # Baixa no estoque
        prod.estoque -= qtd_item
        prod.save()

    # 4. Limpa as variáveis de sessão de carrinho
    request.session['cart'] = {}
    request.session['carrinho'] = {}
    request.session.modified = True
    
    # 5. Envios de e-mails de confirmação e alertas administrativos
    try:
        assunto = f"Nexus Hub - Pedido #{pedido.id} Confirmado!"
        corpo = f"Olá {pedido.cliente.usuario.username}, seu pedido #{pedido.id} de R$ {pedido.total} foi gerado."
        send_mail(assunto, corpo, settings.EMAIL_HOST_USER, [pedido.cliente.usuario.email])
    except Exception as e:
        print(f"Aviso: E-mail não enviado: {e}")
        
    try:
        assunto_admin = f"🚨 NOVO PEDIDO: #{pedido.id}"
        mensagem_admin = f"Novo pedido recebido!\nCliente: {pedido.cliente.usuario.username}\nValor: R$ {pedido.total}"
        send_mail(assunto_admin, mensagem_admin, settings.EMAIL_HOST_USER, ['dono@loja.com'])
    except Exception as e:
        print(f"Aviso: E-mail administrativo não enviado: {e}")
    
    messages.success(request, f"Pedido #{pedido.id} realizado com sucesso!")
    return redirect('loja_meus_pedidos')  # Ajustado para redirecionar para a sua URL existente

# --- HISTÓRICO E DETALHES ---

@login_required
def detalhe_pedido_view(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id, cliente__usuario=request.user)
    itens = pedido.itens.all()
    return render(request, 'detalhe_pedido.html', {
        'pedido': pedido,
        'itens': itens,
        'titulo_aba': 'Detalhes do Pedido | NEXUS Hub',
    })

@login_required
def historico_pedidos_view(request):
    pedidos = Pedido.objects.filter(
        cliente__usuario=request.user
    ).order_by('-data_criacao')
    
    return render(request, 'historico.html', {
        'pedidos': pedidos,
        'titulo_aba': 'Meus Pedidos | NEXUS Hub'
    })

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

@transaction.atomic
@login_required
def cancelar_pedido_view(request, pedido_id):
    # Busca o pedido pertencente ao cliente logado para evitar que cancelem pedidos de outros
    cliente = Cliente.objects.filter(usuario=request.user).first()
    pedido = get_object_or_404(Pedido, id=pedido_id, cliente=cliente)

    # Regra de negócio: Só pode cancelar se o pedido não foi finalizado/entregue ou já cancelado
    # Ajuste as strings ('Pendente', 'Em processamento') conforme os status reais do seu banco
    if pedido.status in ['Cancelado', 'Entregue', 'Finalizado']:
        messages.error(request, f"Este pedido não pode ser cancelado pois seu status atual é '{pedido.status}'.")
        return redirect('loja_meus_pedidos')

    try:
        # 1. Loop pelos itens do pedido para devolver as quantidades de volta ao estoque
        # Modifique 'pedido.itens.all()' se a relação reversa no seu ItemPedido tiver outro 'related_name'
        for item in pedido.itens.all():
            produto = item.produto
            produto.estoque += item.quantidade
            produto.save()

        # 2. Atualiza o status do pedido para Cancelado
        pedido.status = 'Cancelado'
        pedido.save()

        messages.success(request, f"Pedido #{pedido.id} cancelado com sucesso e produtos retornados ao estoque.")
    except Exception as e:
        messages.error(request, f"Erro sistêmico ao processar o cancelamento: {e}")

    return redirect('loja_meus_pedidos')