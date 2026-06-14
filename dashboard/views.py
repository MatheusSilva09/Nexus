import json
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from django.db import transaction
from django.db.models import Sum, Count, F
from django.db.models import Q
from django.db.models.functions import TruncDay
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.core.mail import EmailMessage, send_mail, mail_admins
from django.contrib import messages
from django.utils import timezone
import re

from django.conf import settings
from .models import Produto, ProdutoImagem, Categoria, Loja, Vendedor, Cliente, Pedido, ItemPedido, Carrinho, Venda, Funcionario, Perfil
from .cart import Cart # This import is not used in dashboard views, only in loja views. Can be removed if not used elsewhere.
from .forms import LojaForm, ProdutoForm, ClienteForm
from .decorators import loja_obrigatoria, admin_only_required, vendedor_or_admin_required

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
            return redirect('vitrine')
            
    return render(request, 'signup.html')


# --- DASHBOARD ---

@login_required(login_url='login_view')
def dashboard_view(request):
    # CORREÇÃO PRINCIPAL: Declaramos como None aqui no escopo global da função
    # Isso garante que mesmo o Superusuário tenha essa variável definida
    loja_usuario = None 
    
    # 1. Identificar se é Administrador Global
    if request.user.is_superuser:
        produtos_queryset = Produto.objects.all()
        clientes_queryset = Cliente.objects.all()
        total_funcionarios = Funcionario.objects.count()
        
        # Opcional para o Admin Geral não ver o painel zerado: 
        # Podemos associar à primeira loja cadastrada no banco, se houver
        loja_usuario = Loja.objects.first()
    else:
        # 2. Buscar a loja vinculada ao usuário comum (Lockey)

        # Tenta buscar a loja primeiro através do modelo Perfil
        if hasattr(request.user, 'perfil') and hasattr(request.user.perfil, 'loja'):
            loja_usuario = request.user.perfil.loja
            
        # Redundância 1: Tenta buscar se houver relação direta no User
        elif hasattr(request.user, 'loja'):
            loja_usuario = request.user.loja
            
        # Redundância 2: Tenta buscar pelo funcionário (Ajustado para usar o objeto do usuário de forma segura)
        else:
            funcionario_registro = Funcionario.objects.filter(usuario=request.user).first()
            if funcionario_registro and hasattr(funcionario_registro, 'loja'):
                loja_usuario = funcionario_registro.loja

        # 3. Filtrar as QuerySets com segurança total contra FieldError
        if loja_usuario:
            # Mantemos o filtro apenas em Produto (que sabemos que tem o campo 'loja')
            produtos_queryset = Produto.objects.filter(loja=loja_usuario)
            
            # Evita FieldError: Carrega globalmente por enquanto até ajustarmos as chaves estrangeiras
            clientes_queryset = Cliente.objects.all() 
            total_funcionarios = Funcionario.objects.count()
        else:
            # Se não encontrar nenhuma loja no perfil, zera o inventário por segurança
            produtos_queryset = Produto.objects.none()
            clientes_queryset = Cliente.objects.none()
            total_funcionarios = 0

    # --- CÁLCULO DAS MÉTRICAS ---
    total_itens = produtos_queryset.aggregate(total=Sum('estoque'))['total'] or 0
    
    # 1. Calculamos o valor brute do estoque
    valor_bruto = produtos_queryset.aggregate(total=Sum(F('preco') * F('estoque')))['total'] or 0
    
    # 2. Formatamos o valor diretamente na View para o padrão monetário brasileiro (Ex: 204.159,12)
    valor_estoque_formatado = f"{valor_bruto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # Alertas
    baixo_estoque = produtos_queryset.filter(estoque__gt=0, estoque__lte=F('estoque_minimo')).count()
    alertas_criticos = produtos_queryset.filter(estoque__lte=0).count()

    # Clientes e Funcionários
    total_clientes_ativos = clientes_queryset.count()
    hoje_inicio = timezone.localtime(timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    novos_clientes_hoje = clientes_queryset.filter(data_cadastro__gte=hoje_inicio).count()

    # Tabela de Atividade Recente
    produtos_recentes = produtos_queryset.order_by('-id')[:5]

    context = {
        'total_itens': total_itens,
        'valor_estoque': valor_estoque_formatado,  # String perfeitamente formatada
        'baixo_estoque':baixo_estoque,
        'alertas_criticos': alertas_criticos,
        'total_clientes_ativos': total_clientes_ativos,
        'total_funcionarios': total_funcionarios,
        'novos_clientes_hoje': novos_clientes_hoje,
        'produtos': produtos_recentes,
        'loja_status': "Online",
        'hoje': hoje_inicio.date(),
        'loja_usuario': loja_usuario,
    }

    # Debug para o seu terminal
    print("--- DEBUG NEXUS HUB ---")
    print(f"Usuário: {request.user.username} | Loja detetada: {loja_usuario}")
    
    return render(request, 'dashboard.html', context)

@login_required
def home(request):
    perfil = getattr(request.user, 'perfil', None)
    vendedor = Vendedor.objects.filter(usuario=request.user).first()

    # 1. Superuser ou perfil ADMIN vai para o dashboard principal
    if request.user.is_superuser or (perfil and perfil.nivel == 'ADMIN'):
        return redirect('dashboard')

    # 2. Vendedor aprovado vai para a lista de estoque
    if vendedor and vendedor.aprovado:
        return redirect('lista_estoque')

    # 3. Cliente vai para a vitrine da loja
    perfil = getattr(request.user, 'perfil', None)
    if not request.user.is_superuser and perfil and perfil.nivel == 'CLIENTE':
        return redirect('vitrine')

    # 4. Fallback para vendedores não aprovados ou perfis não tratados
    messages.error(request, "Seu perfil não tem acesso a esta área ou ainda aguarda aprovação.")
    return redirect('login_view')

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
        'titulo_aba': 'Faturamento Diário | NEXUS Hub',
    })
    
# --- ESTOQUE E PRODUTOS ---

def lista_estoque(request):
    # 1. Busca a base de produtos isolada pela loja do usuário logado (Suporta Lockey pelo Perfil)
    if request.user.is_superuser:
        produtos_base = Produto.objects.all()
    else:
        loja_usuario = None
        # Tenta pelo Perfil (Lockey)
        if hasattr(request.user, 'perfil') and hasattr(request.user.perfil, 'loja'):
            loja_usuario = request.user.perfil.loja
        # Redundância: Tenta pela relação direta ou vendedor se houver
        elif hasattr(request.user, 'loja'):
            loja_usuario = request.user.loja
        
        if loja_usuario:
            produtos_base = Produto.objects.filter(loja=loja_usuario)
        else:
            # Caso o usuário ainda use o vínculo antigo por Vendedor
            try:
                produtos_base = Produto.objects.filter(loja__vendedor__usuario=request.user)
            except Exception:
                produtos_base = Produto.objects.none()

    termo_busca = request.GET.get('q', '').strip()
    
    # 2. CALCULA OS ALERTAS (Antes de qualquer filtro de busca)
    alertas_count = produtos_base.filter(estoque__lte=F('estoque_minimo')).count()
    # Adicionamos também o Alerta Crítico (Estoque em zero) que aparece na sua imagem
    alertas_criticos = produtos_base.filter(estoque__lte=0).count()

    # 3. Lógica de filtro (se o usuário clicou para ver apenas baixo estoque)
    produtos = produtos_base
    if request.GET.get('baixo_estoque'):
        produtos = produtos.filter(estoque__lte=F('estoque_minimo'))

    # 4. Agregações de valores brutos
    totais = produtos.aggregate(
        total_itens=Sum('estoque'),
        valor_total=Sum(F('preco') * F('estoque'))
    )

    # 5. Formatação do Valor Monetário para o padrão brasileiro (Evita valor quebrado/longo)
    valor_bruto = totais['valor_total'] or 0
    valor_estoque_formatado = f"{valor_bruto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # 6. Aplica o termo de busca por nome ou descrição se houver
    if termo_busca:
        produtos = produtos.filter(
            Q(nome__icontains=termo_busca) | 
            Q(descricao__icontains=termo_busca)
        )
    
    produtos = produtos.order_by('nome')

    # CORREÇÃO DO CONTEXTO: Incluímos todas as variáveis que a sua tela de estoque precisa
    context = {
        'produtos': produtos,
        'termo_busca': termo_busca,
        'total_itens': totais['total_itens'] or 0,
        'valor_estoque': valor_estoque_formatado,   # String bonita e limpa (R$ 204.159,12)
        'alertas_reposicao': alertas_count,
        'alertas_criticos': alertas_criticos,       # Envia para o card de Ruptura
        'titulo_aba': 'Gerenciamento de Estoque | NEXUS Hub',
    }
    
    # Retorna o arquivo de template correto passando o CONTEXT completo
    # Nota: Certifique-se se o seu arquivo se chama 'estoque_lista.html' ou 'lista_estoque.html'
    return render(request, 'estoque_lista.html', context)

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

@vendedor_or_admin_required
def cadastrar_categoria(request):
    if request.method == "POST":
        nome = request.POST.get('nome')
        if nome:
            novo_slug = slugify(nome)
            
            # Verifica se já existe uma categoria com este slug para evitar o IntegrityError
            if not Categoria.objects.filter(slug=novo_slug).exists():
                categoria = Categoria.objects.create(nome=nome, slug=novo_slug)
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'id': categoria.id, 'nome': categoria.nome})
            else:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': "Esta categoria já está cadastrada."}, status=400)
                messages.warning(request, "Esta categoria já está cadastrada.")
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': "O nome da categoria é obrigatório."}, status=400)

        return redirect('cadastrar_produto')
    return render(request, 'categoria_form.html')

@vendedor_or_admin_required
def editar_categoria_ajax(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)
    if request.method == "POST":
        nome = request.POST.get('nome')
        if nome:
            novo_slug = slugify(nome)
            # Verifica duplicidade excluindo a própria categoria
            if not Categoria.objects.filter(slug=novo_slug).exclude(id=categoria_id).exists():
                categoria.nome = nome
                categoria.slug = novo_slug
                categoria.save()
                return JsonResponse({'success': True, 'id': categoria.id, 'nome': categoria.nome})
            else:
                return JsonResponse({'success': False, 'error': "Esta categoria já está cadastrada."}, status=400)
        return JsonResponse({'success': False, 'error': "O nome da categoria é obrigatório."}, status=400)
    return JsonResponse({'success': False, 'error': "Método não permitido."}, status=405)

@loja_obrigatoria
@vendedor_or_admin_required
def cadastrar_produto(request):
    # 1. Busca a loja vinculada ao usuário
    vendedor_perfil = Vendedor.objects.filter(usuario=request.user).first()
    loja_do_usuario = Loja.objects.filter(vendedor=vendedor_perfil).first()

    if not loja_do_usuario and request.user.is_superuser:
        loja_do_usuario = Loja.objects.first()

    if not loja_do_usuario:
        messages.error(request, "Erro crítico: Nenhuma loja vinculada ao seu perfil encontrada.")
        return redirect('criar_loja')

    if request.method == 'POST':
        post_data = request.POST.copy()
        
        # --- LIMPEZA ROBUSTA CONTRA INVALIDOPERATION (PREÇO ORIGINAL) ---
        preco_raw = post_data.get('preco', '0')
        preco_limpo = re.sub(r'[^\d.,]', '', preco_raw).strip()
        
        if ',' in preco_limpo and '.' in preco_limpo:
            if preco_limpo.rfind('.') < preco_limpo.rfind(','):
                preco_limpo = preco_limpo.replace('.', '')
        preco_limpo = preco_limpo.replace(',', '.')

        try:
            valor_decimal = Decimal(preco_limpo)
            post_data['preco'] = str(valor_decimal)
        except (InvalidOperation, ValueError, TypeError):
            valor_decimal = Decimal('0.00')
            post_data['preco'] = '0.00'

        # --- LIMPEZA ROBUSTA (PREÇO PROMOCIONAL) ---
        preco_promo_raw = post_data.get('preco_promocional', '').strip()
        valor_promo_decimal = None
        
        if preco_promo_raw:
            preco_promo_limpo = re.sub(r'[^\d.,]', '', preco_promo_raw).strip()
            if ',' in preco_promo_limpo and '.' in preco_promo_limpo:
                if preco_promo_limpo.rfind('.') < preco_promo_limpo.rfind(','):
                    preco_promo_limpo = preco_promo_limpo.replace('.', '')
            preco_promo_limpo = preco_promo_limpo.replace(',', '.')
            
            try:
                valor_promo_decimal = Decimal(preco_promo_limpo)
                post_data['preco_promocional'] = str(valor_promo_decimal)
            except (InvalidOperation, ValueError, TypeError):
                post_data['preco_promocional'] = None
        else:
            post_data['preco_promocional'] = None

        # Tratamento do Checkbox booleano (se não vem no POST, o lojista não marcou, logo é False)
        post_data['em_oferta'] = 'em_oferta' in request.POST

        form = ProdutoForm(post_data, request.FILES)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Instancia e associa os dados da loja
                    novo_produto = form.save(commit=False)
                    novo_produto.loja = loja_do_usuario
                    novo_produto.preco = valor_decimal  # Garante o valor sanitizado original
                    
                    # Salva os novos estados de promoção no objeto
                    novo_produto.em_oferta = post_data['em_oferta']
                    novo_produto.preco_promocional = valor_promo_decimal
                    
                    novo_produto.save()

                    # PROCESSAMENTO REAL DO BINÁRIO DA IMAGEM COM ORDENAÇÃO AUTOMÁTICA
                    imagens = request.FILES.getlist('imagens_galeria')
                    
                    if imagens:
                        for indice, img in enumerate(imagens):
                            ProdutoImagem.objects.create(
                                produto=novo_produto, 
                                imagem=img,
                                ordem=indice
                            )
                    else:
                        messages.warning(request, "Nenhuma imagem foi carregada para a galeria deste produto.")

                    messages.success(request, f"Produto '{novo_produto.nome}' cadastrado com sucesso!")
                    return redirect('lista_estoque')
            except Exception as e:
                messages.error(request, f"Erro interno ao salvar os arquivos físicos: {str(e)}")
        else:
            messages.error(request, f"Erro ao validar formulário: {form.errors.as_text()}")
    else:
        form = ProdutoForm()

    categorias = Categoria.objects.all()
    
    return render(request, 'produto_form.html', {
        'form': form, 
        'titulo': 'Cadastrar Novo Produto', 
        'categorias': categorias,
        'titulo_aba': 'Cadastrar Produto | NEXUS Hub'
    })

@login_required
@require_POST
def deletar_imagem_galeria(request, imagem_id):
    try:
        # Busca a imagem garantindo que o produto pertença à loja mapeada pelo usuário
        imagem = ProdutoImagem.objects.get(
            id=imagem_id, 
            produto__loja__vendedor__usuario=request.user
        )
        
        # 1. Deleta o arquivo físico da pasta media/produtos/galeria/
        if imagem.imagem:
            imagem.imagem.delete(save=False)
            
        # 2. Deleta o registro da tabela dashboard_produto do SQLite
        imagem.delete()
        
        print(f"[NEXUS HUB] Imagem ID {imagem_id} deletada com sucesso pelo usuário {request.user}.")
        return JsonResponse({'success': True, 'message': 'Imagem removida com sucesso!'})
        
    except ProdutoImagem.DoesNotExist:
        print(f"[NEXUS HUB] Erro: Imagem ID {imagem_id} não encontrada para o usuário {request.user}.")
        return JsonResponse({'success': False, 'error': 'Imagem não encontrada ou acesso negado.'})
    except Exception as e:
        print(f"[NEXUS HUB] Erro crítico na exclusão: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='login_view')
def editar_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    categorias = Categoria.objects.all()
    
    if request.method == 'POST':
        produto.nome = request.POST.get('nome')
        produto.descricao = request.POST.get('descricao', '')
        
        categoria_id = request.POST.get('categoria')
        produto.categoria = Categoria.objects.filter(id=categoria_id).first()

        estoque_raw = request.POST.get('estoque', '0')
        produto.estoque = int(estoque_raw) if estoque_raw.isdigit() else 0
        
        estoque_min_raw = request.POST.get('estoque_minimo', '5')
        produto.estoque_minimo = int(estoque_min_raw) if estoque_min_raw.isdigit() else 5

        # --- TRATAMENTO ROBUSTO CONTRA INVALIDOPERATION (PREÇO ORIGINAL) ---
        preco_raw = request.POST.get('preco', '0,00')
        preco_limpo = re.sub(r'[^\d.,]', '', preco_raw).strip()
        
        if ',' in preco_limpo and '.' in preco_limpo:
            if preco_limpo.rfind('.') < preco_limpo.rfind(','):
                preco_limpo = preco_limpo.replace('.', '')
        preco_limpo = preco_limpo.replace(',', '.')

        try:
            produto.preco = Decimal(preco_limpo)
        except (InvalidOperation, ValueError, TypeError):
            produto.preco = Decimal('0.00')

        # --- NOVO: TRATAMENTO ROBUSTO (PREÇO PROMOCIONAL) ---
        preco_promo_raw = request.POST.get('preco_promocional', '').strip()
        
        if preco_promo_raw:
            preco_promo_limpo = re.sub(r'[^\d.,]', '', preco_promo_raw).strip()
            if ',' in preco_promo_limpo and '.' in preco_promo_limpo:
                if preco_promo_limpo.rfind('.') < preco_promo_limpo.rfind(','):
                    preco_promo_limpo = preco_promo_limpo.replace('.', '')
            preco_promo_limpo = preco_promo_limpo.replace(',', '.')
            
            try:
                produto.preco_promocional = Decimal(preco_promo_limpo)
            except (InvalidOperation, ValueError, TypeError):
                produto.preco_promocional = None
        else:
            produto.preco_promocional = None

        # Captura o estado do checkbox de promoção (True se marcado, False se omitido)
        produto.em_oferta = 'em_oferta' in request.POST
        
        # Salvamento seguro
        try:
            with transaction.atomic():
                produto.save()
                
                # --- ATUALIZAR ORDEM DAS IMAGENS EXISTENTES ---
                for key, value in request.POST.items():
                    if key.startswith('ordem_imagem_'):
                        img_id = key.replace('ordem_imagem_', '')
                        ProdutoImagem.objects.filter(id=img_id, produto=produto).update(ordem=int(value or 0))

                # --- ADICIONAR NOVAS IMAGENS DA GALERIA ---
                novas_imagens = request.FILES.getlist('imagens_galeria')
                if novas_imagens:
                    # Descobre qual a maior ordem atual para continuar a sequência de onde parou
                    ultima_imagem = produto.imagens.all().order_by('-ordem').first()
                    proxima_ordem = (ultima_imagem.ordem + 1) if ultima_imagem else 0
                    
                    for img in novas_imagens:
                        ProdutoImagem.objects.create(
                            produto=produto, 
                            imagem=img, 
                            ordem=proxima_ordem
                        )
                        proxima_ordem += 1
                
                messages.success(request, f"Produto '{produto.nome}' atualizado com sucesso!")
                return redirect('lista_estoque')
                
        except Exception as e:
            messages.error(request, f"Erro ao atualizar no banco: {e}")
    
    # Formatações de saída para renderizar no formulário HTML
    preco_formatado = f"{produto.preco:.2f}".replace('.', ',')
    preco_promo_formatado = f"{produto.preco_promocional:.2f}".replace('.', ',') if produto.preco_promocional else ""
    
    imagens_atuais = produto.imagens.all().order_by('ordem', 'id')

    return render(request, 'editar_produto.html', {
        'produto': produto, 
        'preco_formatado': preco_formatado,
        'preco_promo_formatado': preco_promo_formatado,  # Passamos o preço promocional limpo
        'categorias': categorias,
        'imagens_atuais': imagens_atuais,
        'titulo_aba': 'Editar Produto | NEXUS Hub'
    })

@login_required(login_url='login_view')
def detalhe_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    imagens = produto.imagens.all()
    return render(request, 'produto_detalhe.html', {
        'produto': produto,
        'imagens': imagens,
    })

@login_required(login_url='login_view')
def excluir_produto(request, produto_id):
    # Bloqueio para Vendedores: não podem deletar produtos do sistema
    if not request.user.is_superuser and request.user.perfil.nivel == 'VENDEDOR':
        messages.error(request, "Você não tem permissão para excluir produtos do catálogo.")
        return redirect('lista_estoque')
    # Busca o produto garantindo que ele pertença à loja do usuário
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    
    if request.method == 'POST':
        produto.delete()
        return redirect('lista_estoque')
        
    return render(request, 'confirmar_exclusao_produto.html', {'produto': produto})

# --- PEDIDO ---

@login_required(login_url='login_view')
def alternar_status_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, loja=request.user.vendedor.loja)
    produto.ativo = not produto.ativo
    produto.save()
    return redirect('gerenciamento_estoque')

# --- VIEWS DO CARRINHO (CLIENT-FACING) ---


# --- CLIENTES ---

@login_required
def profile(request):
    return render(request, "profile.html")
    
@login_required(login_url='login_view')
def lista_clientes(request):
    clientes = Cliente.objects.all()
    return render(request, 'lista_clientes.html', {
        'clientes': clientes,
        'titulo_aba': 'Lista de Clientes | NEXUS Hub'})

@login_required(login_url='login_view')
def cadastrar_cliente(request):
    if request.method == 'POST':
        # 1. Pegamos os dados do formulário
        nome = request.POST.get('nome')
        telefone = request.POST.get('telefone')
        email = request.POST.get('email')
        endereco = request.POST.get('endereco')

        # Trava de segurança: impede Vendedores de acessar
        if not request.user.is_superuser and request.user.perfil.nivel == 'VENDEDOR':
            messages.error(request, "Você não tem permissão para cadastrar clientes.")
            return redirect('dashboard')

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

    return render(request, 'cliente_form.html', {
        'titulo_aba': 'Cadastrar Cliente | NEXUS Hub',
    })

@login_required(login_url='login_view')
def editar_cliente(request, pk):

    if not request.user.is_superuser and request.user.perfil.nivel == 'VENDEDOR':
        messages.error(request, "Você não tem permissão para editar clientes.")
        return redirect('lista_clientes')
    cliente = get_object_or_404(Cliente, pk=pk)
    
    if request.method == 'POST':
        cliente.nome = request.POST.get('nome')
        cliente.telefone = request.POST.get('telefone')
        cliente.email = request.POST.get('email')
        cliente.endereco = request.POST.get('endereco')
        cliente.save()
        return redirect('lista_clientes')
    
    return render(request, 'cliente_form.html', {
        'cliente': cliente,
        'titulo_aba': 'Editar Cliente | NEXUS Hub',
    })

@login_required(login_url='login_view')
def excluir_cliente(request, pk):

    if not request.user.is_superuser and request.user.perfil.nivel == 'VENDEDOR':
        messages.error(request, "Você não tem permissão para excluir clientes.")
        return redirect('lista_clientes')
    cliente = get_object_or_404(Cliente, pk=pk)
    
    if request.method == 'POST':
        cliente.delete()
        messages.success(request, f"Cliente {cliente.nome} removido com sucesso.")
        return redirect('lista_clientes')
        
    return render(request, 'confirmar_exclusao_cliente.html', {'cliente': cliente})

# --- GESTÃO DE LOJA ---

@vendedor_or_admin_required
def criar_loja(request):
    # ... (mantenha a lógica de permissão que já tem) ...

    if request.method == 'POST':
        form = LojaForm(request.POST)
        if form.is_valid():
            # commit=False permite modificar o objeto antes de salvar no banco
            nova_loja = form.save(commit=False)
            
            # Aqui está a correção: vinculamos o vendedor logado
            # Supondo que você use o modelo Vendedor ou Perfil para identificar o dono
            try:
                # Se o seu sistema usa 'Vendedor' para lojas:
                nova_loja.vendedor = Vendedor.objects.get(usuario=request.user)
                nova_loja.save()
                
                messages.success(request, f"Loja '{nova_loja.nome}' criada com sucesso!")
                return redirect('ver_loja')
            except Vendedor.DoesNotExist:
                messages.error(request, "Você precisa estar cadastrado como vendedor para criar uma loja.")
                return redirect('home')
        else:
            # Caso o form seja inválido, ele mostrará os erros no HTML
            pass 
    else:
        form = LojaForm()
    
    return render(request, 'criar_loja.html', {
        'form': form,
        'titulo_aba': 'Criar Loja | NEXUS Hub',
    })
@vendedor_or_admin_required
def editar_loja(request):
    vendedor = Vendedor.objects.filter(usuario=request.user).first()
    loja = get_object_or_404(Loja, vendedor=vendedor)

    if request.method == 'POST':
        # O segredo da edição é o parâmetro 'instance'
        form = LojaForm(request.POST, request.FILES, instance=loja)
        if form.is_valid():
            form.save()
            messages.success(request, "Configurações da loja atualizadas!")
            return redirect('ver_loja')
    else:
        form = LojaForm(instance=loja)
    
    return render(request, 'editar_loja.html', {
        'form': form, 'loja': loja, 'titulo': 'Editar Informações da Loja',
        'titulo_aba': 'Editar Loja | NEXUS Hub',
    })
@vendedor_or_admin_required
def ver_loja(request):
    vendedor = Vendedor.objects.filter(usuario=request.user).first()
    loja = Loja.objects.filter(vendedor=vendedor).first()
    if not loja:
        return redirect('criar_loja')
    return render(request, 'ver_loja.html', {'loja': loja})

@login_required
@login_required(login_url='login_view')
def excluir_loja(request):
    # 1. Busca o vendedor vinculado ao usuário logado
    vendedor = Vendedor.objects.filter(usuario=request.user).first()

    # Trava de segurança máxima: apenas DONO ou Superusuário deletam a loja
    if not request.user.is_superuser and request.user.perfil.nivel in ['GERENTE', 'VENDEDOR']:
        messages.error(request, "Ação não permitida. Apenas o Dono da loja pode excluí-la.")
        return redirect('dashboard')
    
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

@login_required(login_url='login_view')
def adicionar_funcionario(request):
    if request.method == 'POST':
        nome = request.POST.get('nome')
        cargo = request.POST.get('cargo')
        email = request.POST.get('email')
        telefone = request.POST.get('telefone')  # Capturando o telefone do formulário

        # Trava de segurança: impede Vendedores de acessar
        if not request.user.is_superuser and request.user.perfil.nivel == 'VENDEDOR':
            messages.error(request, "Você não tem permissão para cadastrar funcionários.")
            return redirect('dashboard')
            
        # Proteção contra e-mail duplicado na equipe
        if Funcionario.objects.filter(email=email).exists():
            messages.error(request, "Este funcionário já está cadastrado.")
            # Retorna mantendo os dados digitados preenchidos nos inputs
            return render(request, 'funcionario_form.html', {
                'form': request.POST,
                'titulo_aba': 'Adicionar Funcionário | NEXUS Hub',
            })

        # Criação do objeto (removida a data_admissao pois o auto_now_add já cuida disso)
        Funcionario.objects.create(
            nome=nome,
            cargo=cargo,
            email=email,
            telefone=telefone,
            usuario_id=request.user
        )
        
        messages.success(request, "Funcionário adicionado com sucesso!")
        return redirect('lista_funcionarios')

    # Retorno via GET (Carregamento inicial da página)
    return render(request, 'funcionario_form.html', {
        'form': {},  # Dicionário vazio evita o VariableDoesNotExist nos inputs
        'titulo_aba': 'Adicionar Funcionário | NEXUS Hub',
    })

@login_required(login_url='login_view')
def lista_funcionarios(request):
    # Se for admin, mostra todos os funcionários
    if request.user.is_superuser:
        funcionarios = Funcionario.objects.all()
    else:
        # Se for vendedor, mostra apenas seus funcionários
        funcionarios = Funcionario.objects.filter(usuario_id=request.user)
    
    return render(request, 'lista_funcionarios.html', {
        'funcionarios': funcionarios,
        'titulo_aba': 'Lista de Funcionários | NEXUS Hub',
    })
@login_required(login_url='login_view')
def editar_funcionario(request, id):
    if not request.user.is_superuser and request.user.perfil.nivel == 'VENDEDOR':
        messages.error(request, "Você não tem permissão para editar funcionários.")
        return redirect('lista_funcionarios')
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
    
    return render(request, 'editar_funcionario.html', {
        'funcionario': funcionario,
        'titulo_aba': 'Editar Funcionário | NEXUS Hub',
    })
@vendedor_or_admin_required
def excluir_funcionario(request, id):
    if not request.user.is_superuser and request.user.perfil.nivel == 'VENDEDOR':
        messages.error(request, "Você não tem permissão para excluir funcionários.")
        return redirect('lista_funcionarios')
    else:
        funcionario = get_object_or_404(Funcionario, id=id, usuario_id=request.user)
    
    funcionario.delete()
    # Mensagem de sucesso opcional para feedback ao usuário
    # messages.success(request, f"Funcionário {funcionario.nome} removido com sucesso.")
    return redirect('lista_funcionarios')

@vendedor_or_admin_required
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
