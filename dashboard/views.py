import json
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from django.db import transaction
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDay
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.core.mail import EmailMessage, send_mail, mail_admins
from django.contrib import messages
from django.utils import timezone

from django.conf import settings
from .models import Produto, ProdutoImagem, Categoria, Loja, Vendedor, Cliente, Pedido, ItemPedido, Carrinho, Venda, Funcionario
from .cart import Cart
from .forms import LojaForm, ProdutoForm, ClienteForm
from .decorators import loja_obrigatoria, admin_only_required, vendedor_restrito_required

# --- AUTENTICAÇÃO ---

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        user_nome = request.POST.get('username')
        senha = request.POST.get('password')
        user = authenticate(request, username=user_nome, password=senha)
        
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login_view')

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        user_nome = request.POST.get('username')
        email = request.POST.get('email')
        senha = request.POST.get('password')
        
        if User.objects.filter(username=user_nome).exists():
            messages.error(request, 'Este nome de usuário já está em uso.')
        else:
            user = User.objects.create_user(username=user_nome, email=email, password=senha)
            # O sinal 'create_user_profile' em models.py criará o Perfil automaticamente como 'CLIENTE'
            login(request, user)
            messages.success(request, f'Bem-vindo, {user_nome}! Sua conta foi criada.')
            return redirect('vitrine_produtos')
            
    return render(request, 'signup.html')


# --- DASHBOARD ---

@admin_only_required
@login_required(login_url='login_view')
def dashboard_view(request):
    # 1. Total de itens físicos (Soma da coluna estoque)
    total_itens = Produto.objects.aggregate(total=Sum('estoque'))['total'] or 0

    # 2. Valor financeiro do estoque
    valor_estoque = Produto.objects.all().aggregate(
        total=Sum(F('preco') * F('estoque'))
    )['total'] or 0

    # 3. Alertas de reposição
    alertas_reposicao = Produto.objects.filter(estoque__lte=F('estoque_minimo')).count()

    # 4. Total de Clientes
    total_clientes_ativos = Cliente.objects.count()
    
    hoje = timezone.now().date()
    novos_clientes_hoje = Cliente.objects.filter(data_cadastro__date=hoje).count()

    # 5. Produtos para a tabela de 'Atividade Recente'
    produtos_recentes = Produto.objects.all().order_by('-id')[:5]

    context = {
        'total_itens': total_itens,
        'valor_estoque': valor_estoque,
        'alertas_reposicao': alertas_reposicao,
        'total_clientes_ativos': total_clientes_ativos,
        'novos_clientes_hoje': novos_clientes_hoje,
        'produtos': produtos_recentes,
        'loja_status': "Online",
        'hoje': hoje,
    }

    # Print de teste para confirmar no seu terminal
    print("--- DEBUG NEXUS HUB ---")
    print(f"Itens: {total_itens} | Valor: {valor_estoque}")
    
    return render(request, 'dashboard.html', context)
@login_required
def home(request):
    # 1. Se for cliente, vai para a vitrine
    perfil = getattr(request.user, 'perfil', None)
    if perfil and perfil.nivel == 'CLIENTE':
        return redirect('vitrine_produtos')

    # Verifica se é um vendedor aprovado (não admin)
    vendedor = Vendedor.objects.filter(usuario=request.user).first()
    if vendedor and vendedor.aprovado and not request.user.is_superuser:
        # Redireciona vendedor para lista de estoque
        return redirect('lista_estoque')
    
    # Admin continua para o dashboard
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        messages.error(request, "Perfil não encontrado. Contate o suporte.")
        return redirect('logout')
    
    if perfil.nivel == 'ADMIN':
        produtos_loja = Produto.objects.all()
    else:
        produtos_loja = Produto.objects.filter(loja=perfil.loja)

    total_estoque = produtos_loja.aggregate(total=Sum(F('preco') * F('estoque')))['total'] or 0
    avisos = produtos_loja.filter(estoque__lte=F('estoque_minimo')).count()
    
    context = {
        'receita': total_estoque,
        'vendas': produtos_loja.count(),
        'avisos': avisos,
        'produtos': produtos_loja[:5],
        'nivel': perfil.nivel,
    }
    return render(request, 'dashboard.html', context)

def dashboard_faturamento(request):
    dados_vendas = (
        Pedido.objects.filter(pago=True)
        .annotate(dia=TruncDay('data_criacao'))
        .values('dia')
        .annotate(total_dia=Sum('total'))
        .order_by('dia')
    )

    labels = [d['dia'].strftime('%d/%m') for d in dados_vendas]
    valores = [float(d['total_dia']) for d in dados_vendas]

    return render(request, 'admin_stats.html', {
        'labels': json.dumps(labels),
        'valores': json.dumps(valores),
    })
    
# --- ESTOQUE E PRODUTOS ---

@loja_obrigatoria
def lista_estoque(request):
    # 1. Busca a base de produtos do usuário logado
    produtos_base = Produto.objects.filter(loja__vendedor__usuario=request.user)
    
    # 2. CALCULA OS ALERTAS (Antes de qualquer filtro de busca)
    # Aqui definimos a variável que estava faltando
    alertas_count = produtos_base.filter(estoque__lte=F('estoque_minimo')).count()

    # 3. Lógica de filtro (se o usuário clicou para ver apenas baixo estoque)
    produtos = produtos_base
    if request.GET.get('baixo_estoque'):
        produtos = produtos.filter(estoque__lte=F('estoque_minimo'))

    # 4. Agregações de valores
    totais = produtos.aggregate(
        total_itens=Sum('estoque'), # Soma a quantidade total de peças
        valor_total=Sum(F('preco') * F('estoque')) # Valor total em R$
    )

    context = {
        'produtos': produtos,
        'total_itens': totais['total_itens'] or 0,
        'valor_estoque': totais['valor_total'] or 0,
        'alertas_reposicao': alertas_count, # Agora a variável existe!
    }
    return render(request, 'estoque_lista.html', context)

class ListaEstoqueView(LoginRequiredMixin, ListView):
    login_url = 'login_view'
    model = Produto
    template_name = 'estoque.html'

    def get_queryset(self):
        vendedor = Vendedor.objects.get(usuario=self.request.user)
        return Produto.objects.filter(loja__vendedor=vendedor)

def vitrine_produtos(request):
    query = request.GET.get('q')
    categoria_id = request.GET.get('categoria')
    
    produtos = Produto.objects.filter(estoque__gt=0, ativo=True)
    
    if query:
        produtos = produtos.filter(nome__icontains=query)
    if categoria_id:
        produtos = produtos.filter(categoria_id=categoria_id)

    categorias = Categoria.objects.all()
    
    return render(request, 'vitrine.html', {
        'produtos': produtos,
        'categorias': categorias,
        'titulo_aba': 'Vitrine | NEXUS Hub',
        'query': query
    })

def cadastrar_categoria(request):
    if request.method == "POST":
        nome = request.POST.get('nome')
        if nome:
            novo_slug = slugify(nome)
            
            # Verifica se já existe uma categoria com este slug para evitar o IntegrityError
            if not Categoria.objects.filter(slug=novo_slug).exists():
                Categoria.objects.create(nome=nome, slug=novo_slug)
            else:
                # Opcional: Adicionar uma mensagem de aviso que a categoria já existe
                from django.contrib import messages
                messages.warning(request, "Esta categoria já está cadastrada.")
                
        return redirect('cadastrar_produto')
    return render(request, 'categoria_form.html')

@vendedor_restrito_required
def cadastrar_produto(request):
    if request.method == 'POST':
        # 1. Processa os dados básicos do formulário
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao')
        preco = request.POST.get('preco')
        estoque = request.POST.get('estoque')
        categoria_id = request.POST.get('categoria')
        
        # 2. BUSCA DE INSTÂNCIAS (O Ponto Crítico)
        # Primeiro, pegamos o perfil de Vendedor do usuário logado
        vendedor_perfil = Vendedor.objects.filter(usuario=request.user).first()
        
        # Agora, buscamos a Loja vinculada a esse perfil de Vendedor
        loja_do_usuario = None
        if vendedor_perfil:
            loja_do_usuario = Loja.objects.filter(vendedor=vendedor_perfil).first()

        # 3. VALIDAÇÃO E CRIAÇÃO
        if loja_do_usuario:
            novo_produto = Produto.objects.create(
                nome=nome,
                descricao=descricao,
                preco=preco,
                estoque=estoque,
                categoria_id=categoria_id,
                loja=loja_do_usuario, # Passa a instância correta da Loja
            )

            # 4. FUNÇÃO PARA MÚLTIPLAS IMAGENS
            imagens = request.FILES.getlist('imagens_galeria')
            print(f"DEBUG: Imagens recebidas: {len(imagens)}")  # Debug temporário
            for img in imagens:
                print(f"DEBUG: Salvando imagem: {img.name}")  # Debug temporário
                ProdutoImagem.objects.create(produto=novo_produto, imagem=img)

            messages.success(request, f"Produto '{nome}' cadastrado com sucesso!")
            return redirect('lista_estoque')
        
        else:
            # Caso o vendedor não tenha loja cadastrada no Admin
            messages.error(request, "Erro: Nenhuma loja vinculada ao seu perfil. Contate o administrador.")
            return redirect('cadastrar_produto')

    else:
        form = ProdutoForm()
        
    categorias = Categoria.objects.all() # Garante que as categorias apareçam no select
    
    return render(request, 'produto_form.html', {
        'form': form, 
        'titulo': 'Cadastrar Novo Produto', 
        'categorias': categorias
    })

@login_required
def editar_produto(request, produto_id):
    # Mantendo sua segurança de busca por usuário
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    categorias = Categoria.objects.all()
    
    if request.method == 'POST':
        # 1. Pegamos os dados simples
        produto.nome = request.POST.get('nome')
        produto.descricao = request.POST.get('descricao', '')
        
        # 2. Tratamos a Categoria
        categoria_id = request.POST.get('categoria')
        produto.categoria = Categoria.objects.filter(id=categoria_id).first()

        # 3. Tratamos os números inteiros
        estoque_raw = request.POST.get('estoque', '0')
        produto.estoque = int(estoque_raw) if estoque_raw.isdigit() else 0
        
        estoque_min_raw = request.POST.get('estoque_minimo', '5')
        produto.estoque_minimo = int(estoque_min_raw) if estoque_min_raw.isdigit() else 5

        # 4. Tratamos o Preço (Limpando antes de salvar no objeto)
        preco_raw = request.POST.get('preco', '0,00')
        try:
            # Usando sua lógica de limpeza completa para evitar erros
            preco_limpo = preco_raw.replace('R$', '').replace('.', '').replace(',', '.').strip()
            produto.preco = Decimal(preco_limpo)
        except:
            produto.preco = Decimal('0.00')
        
        # 5. Agora sim, salvamos o objeto completo
        try:
            produto.save()
            messages.success(request, f"Produto '{produto.nome}' atualizado com sucesso!")
            return redirect('lista_estoque')
        except Exception as e:
            messages.error(request, f"Erro ao atualizar: {e}")
    
    # O contexto unificado que você já estava usando
    return render(request, 'editar_produto.html', {
        'produto': produto, 
        'categorias': categorias
    })

@login_required
def detalhe_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    imagens = produto.imagens.all()
    return render(request, 'produto_detalhe.html', {
        'produto': produto,
        'imagens': imagens,
    })

@login_required
def excluir_produto(request, produto_id):
    # Busca o produto garantindo que ele pertença à loja do usuário
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    
    if request.method == 'POST':
        produto.delete()
        return redirect('lista_estoque')
        
    return render(request, 'confirmar_exclusao_produto.html', {'produto': produto})

@vendedor_restrito_required
def alternar_status_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, loja=request.user.vendedor.loja)
    produto.ativo = not produto.ativo
    produto.save()
    return redirect('gerenciamento_estoque')

def adicionar_ao_carrinho(request, produto_id):
    cart = Cart(request)
    produto = get_object_or_404(Produto, id=produto_id)
    cart.add(produto_id=produto.id)
    return redirect('vitrine_produtos')

def ver_carrinho(request):
    cart = Cart(request)
    itens_carrinho = []
    total_geral = 0

    # Percorre os IDs guardados na sessão
    for produto_id, dados in cart.cart.items():
        produto = Produto.objects.get(id=produto_id)
        subtotal = produto.preco * dados['quantidade']
        total_geral += subtotal
        
        itens_carrinho.append({
            'produto': produto,
            'quantidade': dados['quantidade'],
            'subtotal': subtotal
        })

    return render(request, 'carrinho.html', {
        'itens': itens_carrinho,
        'total': total_geral,
        'titulo_aba': 'Carrinho | NEXUS Hub'
    })
    
def remover_do_carrinho(request, produto_id):
    cart = Cart(request)
    cart.remove(produto_id)
    return redirect('ver_carrinho')

@transaction.atomic
@login_required
def finalizar_pedido(request):
    cart = Cart(request)
    if not cart.cart:
        return redirect('vitrine_produtos')

    # 1. Recupera o cadastro de Cliente do usuário logado
    cliente = Cliente.objects.filter(usuario=request.user).first()

    if not cliente:
        messages.warning(request, "Por favor, complete seus dados de entrega antes de finalizar a compra.")
        return redirect('cadastrar_cliente')

    # 2. Otimização: Busca todos os produtos do carrinho de uma só vez
    ids_produtos = cart.cart.keys()
    produtos_dict = {p.id: p for p in Produto.objects.filter(id__in=ids_produtos)}

    # Calcula o total usando o dicionário em memória
    total_geral = sum(produtos_dict[int(id)].preco * item['quantidade'] 
                      for id, item in cart.cart.items())
    
    # Cria o Pedido principal
    pedido = Pedido.objects.create(cliente=cliente, total=total_geral)

    # 3. Transfere os itens da Sessão para o Banco (ItemPedido)
    for produto_id, dados in cart.cart.items():
        produto = produtos_dict[int(produto_id)]
        
        ItemPedido.objects.create(
            pedido=pedido,
            produto=produto,
            preco=produto.preco,
            quantidade=dados['quantidade']
        )

        # Baixa no estoque
        produto.estoque -= dados['quantidade']
        produto.save()

    # 4. Limpa o carrinho
    request.session['cart'] = {}
    
    # 5. Processamento de E-mail (Protegido por try/except)
    try:
        # Monta o e-mail
        assunto = f"Nexus Hub - Pedido #{pedido.id} Confirmado!"
        corpo = f"Olá {pedido.cliente.usuario.username}, seu pedido #{pedido.id} foi recebido com sucesso."
        destinatario = [pedido.cliente.usuario.email]

        send_mail(assunto, corpo, settings.EMAIL_HOST_USER, destinatario)
        
    except Exception as e:
        print(f"Aviso: Não foi possível enviar o e-mail. Erro: {e}")
        
    # 6. Notificação para o Administrador
    try:
        assunto_admin = f"🚨 NOVO PEDIDO: #{pedido.id}"
        mensagem_admin = f"""
        Um novo pedido foi finalizado no Nexus Hub!
        Cliente: {pedido.cliente.usuario.username}
        Valor Total: R$ {pedido.total}
        Data: {pedido.data_criacao.strftime('%d/%m/%Y %H:%M')}

        Acesse o painel para gerenciar a entrega.
        """
        email_admin = 'dono@loja.com'

        send_mail(
            assunto_admin,
            mensagem_admin,
            settings.EMAIL_HOST_USER,
            [email_admin],
            fail_silently=False,
        )
        
        # Dispara o e-mail para todos da lista ADMINS
        mail_admins(
            f"Novo Pedido #{pedido.id}",
            f"O cliente {pedido.cliente.usuario.username} acabou de comprar R$ {pedido.total}.",
        )
    except Exception as e:
        print(f"Erro ao notificar admin: {e}")
    
    messages.success(request, f"Pedido #{pedido.id} realizado com sucesso! Acompanhe o status abaixo.")
    return redirect('historico_pedidos')

@login_required
def detalhe_pedido(request, pedido_id):
    # Busca o pedido ou retorna 404 se não existir
    # Filtramos pelo usuario do cliente logado por segurança
    pedido = get_object_or_404(Pedido, id=pedido_id, cliente__usuario=request.user)
    
    itens = pedido.itens.all()
    
    return render(request, 'detalhe_pedido.html', {
        'pedido': pedido,
        'itens': itens
    })
@login_required
def historico_pedidos(request):
    # Busca todos os pedidos vinculados ao usuário logado através do modelo Cliente
    # .order_by('-data_criacao') garante que o mais recente apareça primeiro
    pedidos = Pedido.objects.filter(
        cliente__usuario=request.user
    ).order_by('-data_criacao')
    
    return render(request, 'historico.html', {
        'pedidos': pedidos,
        'titulo_aba': 'Meus Pedidos | NEXUS Hub'
    })

# --- CLIENTES ---

@login_required
def profile(request):
    return render(request, "profile.html")

@login_required
def lista_clientes(request):
    clientes = Cliente.objects.all()
    return render(request, 'lista_clientes.html', {'clientes': clientes})

@login_required # Garante que só usuários logados acessem
def cadastrar_cliente(request):
    if request.method == 'POST':
        # 1. Pegamos os dados do formulário
        nome = request.POST.get('nome')
        telefone = request.POST.get('telefone')
        email = request.POST.get('email')
        endereco = request.POST.get('endereco')

        # 2. VALIDAÇÃO DE INTEGRIDADE: Verifica se o e-mail já existe (caso seja unique no model)
        if email and Cliente.objects.filter(email=email).exists():
            messages.error(request, "Este e-mail já está cadastrado para outro cliente.")
            return render(request, 'cliente_form.html', {
                'nome': nome, 'telefone': telefone, 'endereco': endereco
            })

        # 3. Criamos o objeto vinculado ao usuário logado
        try:
            novo_cliente = Cliente(
                nome=nome,
                telefone=telefone,
                email=email,
                endereco=endereco,
                usuario=request.user
            )
            
            # 4. Salvamento seguro
            novo_cliente.save()
            messages.success(request, f"Cliente {nome} cadastrado com sucesso!")
            return redirect('lista_clientes')
            
        except Exception as e:
            # Captura qualquer outro erro de integridade não previsto
            messages.error(request, "Erro ao salvar: Verifique se os dados estão repetidos.")
            return render(request, 'cliente_form.html')

    return render(request, 'cliente_form.html')

@login_required
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk, usuario=request.user)
    
    if request.method == 'POST':
        cliente.nome = request.POST.get('nome')
        cliente.telefone = request.POST.get('telefone')
        cliente.email = request.POST.get('email')
        cliente.endereco = request.POST.get('endereco')
        cliente.save()
        return redirect('lista_clientes')

    return render(request, 'cliente_form.html', {'cliente': cliente})

@login_required
def excluir_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk, usuario=request.user)
    cliente.delete()
    return redirect('lista_clientes')

# --- GESTÃO DE LOJA ---

@login_required
def criar_loja(request):
    vendedor = get_object_or_404(Vendedor, usuario=request.user)
    
    # Se já tiver loja, redireciona para a edição para evitar duplicidade
    if Loja.objects.filter(vendedor=vendedor).exists():
        return redirect('editar_loja')

    if request.method == 'POST':
        form = LojaForm(request.POST)
        if form.is_valid():
            loja = form.save(commit=False)
            loja.vendedor = vendedor
            loja.save()
            messages.success(request, "Loja criada com sucesso!")
            return redirect('ver_loja')
    else:
        form = LojaForm()
    
    return render(request, 'editar_loja.html', {'form': form, 'titulo': 'Criar Nova Loja'})

@login_required
def editar_loja(request):
    vendedor = get_object_or_404(Vendedor, usuario=request.user)
    loja = get_object_or_404(Loja, vendedor=vendedor)

    if request.method == 'POST':
        # O segredo da edição é o parâmetro 'instance'
        form = LojaForm(request.POST, instance=loja)
        if form.is_valid():
            form.save()
            messages.success(request, "Configurações da loja atualizadas!")
            return redirect('ver_loja')
    else:
        form = LojaForm(instance=loja)
    
    return render(request, 'editar_loja.html', {'form': form, 'loja': loja, 'titulo': 'Editar Informações da Loja'})

@login_required
def ver_loja(request):
    vendedor = Vendedor.objects.filter(usuario=request.user).first()
    loja = Loja.objects.filter(vendedor=vendedor).first()
    if not loja:
        return redirect('criar_loja')
    return render(request, 'ver_loja.html', {'loja': loja})

@login_required
def excluir_loja(request):
    # 1. Busca o vendedor vinculado ao usuário logado
    vendedor = Vendedor.objects.filter(usuario=request.user).first()
    
    if not vendedor:
        messages.error(request, "Perfil de vendedor não encontrado.")
        return redirect('home')

    # 2. Busca a loja deste vendedor
    loja = Loja.objects.filter(vendedor=vendedor).first()

    if request.method == 'POST':
        if loja:
            loja.delete()
            messages.success(request, "Sua loja foi excluída com sucesso.")
            return redirect('home')
        else:
            messages.warning(request, "Você não possui uma loja ativa para excluir.")
            return redirect('home')

    # Se for GET (página de confirmação)
    if not loja:
        messages.warning(request, "Nenhuma loja encontrada para exclusão.")
        return redirect('home')
        
    return render(request, 'dashboard/confirm_delete.html', {'loja': loja})

@login_required
def adicionar_funcionario(request):
    if request.method == 'POST':
        nome = request.POST.get('nome')
        cargo = request.POST.get('cargo')
        email = request.POST.get('email')
        
        # Proteção contra e-mail duplicado na equipe
        if Funcionario.objects.filter(email=email).exists():
            messages.error(request, "Este funcionário já está cadastrado.")
            return render(request, 'funcionario_form.html')

        Funcionario.objects.create(
            nome=nome,
            cargo=cargo,
            email=email,
            usuario_id=request.user,
            data_admissao=request.POST.get('data_admissao')
        )
        messages.success(request, "Funcionário adicionado com sucesso!")
        return redirect('lista_funcionarios') # Ou a página que você preferir

    return render(request, 'funcionario_form.html')

@login_required
def lista_funcionarios(request):
    # Se for admin, mostra todos os funcionários
    if request.user.is_superuser:
        funcionarios = Funcionario.objects.all()
    else:
        # Se for vendedor, mostra apenas seus funcionários
        funcionarios = Funcionario.objects.filter(usuario_id=request.user)
    
    return render(request, 'lista_funcionarios.html', {'funcionarios': funcionarios})

@login_required
def editar_funcionario(request, id):
    # Verifica permissão: admin vê todos, vendedor vê só seus
    if request.user.is_superuser:
        funcionario = get_object_or_404(Funcionario, id=id)
    else:
        funcionario = get_object_or_404(Funcionario, id=id, usuario_id=request.user)
    
    if request.method == "POST":
        funcionario.nome = request.POST.get('nome')
        funcionario.cargo = request.POST.get('cargo')
        funcionario.email = request.POST.get('email')
        funcionario.telefone = request.POST.get('telefone')
        funcionario.endereco = request.POST.get('endereco')
        
        # Garante que a data de admissão nunca seja nula
        if not funcionario.data_admissao:
            funcionario.data_admissao = timezone.now().date()
            
        funcionario.save()
        return redirect('lista_funcionarios')
    
    return render(request, 'editar_funcionario.html', {'funcionario': funcionario})

@login_required
def excluir_funcionario(request, id):
    # Verifica permissão: admin deleta todos, vendedor deleta só seus
    if request.user.is_superuser:
        funcionario = get_object_or_404(Funcionario, id=id)
    else:
        funcionario = get_object_or_404(Funcionario, id=id, usuario_id=request.user)
    
    funcionario.delete()
    # Mensagem de sucesso opcional para feedback ao usuário
    # messages.success(request, f"Funcionário {funcionario.nome} removido com sucesso.")
    return redirect('lista_funcionarios')

@vendedor_restrito_required
@transaction.atomic
def realizar_venda(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    
    if produto.estoque <= 0:
        messages.error(request, f"O produto {produto.nome} está sem estoque!")
        return redirect('lista_estoque')

    # Diminui 1 unidade do estoque
    produto.estoque -= 1
    produto.save()
    
    # Cria o registro da venda (ajuste os campos conforme seu modelo Venda)
    Venda.objects.create(
        vendedor=request.user,
        produto=produto,
        quantidade=1,
        valor_total=produto.preco
    )
    
    messages.success(request, f"Venda de {produto.nome} realizada com sucesso!")
    return redirect('lista_estoque')
