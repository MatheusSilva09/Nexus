import json
from multiprocessing import context
from urllib import request

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from django.db import transaction
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDay
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.utils.text import slugify

from nexus import settings
from .models import Produto, Categoria, Loja, Vendedor
from .cart import Cart
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.core.mail import EmailMessage, send_mail, mail_admins
from django.template.loader import render_to_string
from weasyprint import HTML
from .forms import LojaForm, ProdutoForm
from .decorators import loja_obrigatoria
from decimal import Decimal
from django.contrib import messages

from .models import Cliente, Loja, Produto, Pedido, ItemPedido, Carrinho, Vendedor, Venda, Funcionario
from .forms import ClienteForm
from django.utils import timezone

# --- AUTENTICAÇÃO ---

def login_view(request):
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

@loja_obrigatoria
def lista_estoque(request):
    # Otimizamos a busca usando o perfil do vendedor
    vendedor = Vendedor.objects.get(usuario=request.user)
    
    # Filtramos os produtos que pertencem à loja do vendedor logado
    produtos = Produto.objects.filter(loja__vendedor=vendedor)
    
    return render(request, 'estoque.html', {'produtos': produtos})

@loja_obrigatoria
def lista_clientes(request):
    # Sua lógica de clientes aqui...
    return render(request, 'clientes.html')

# --- DASHBOARD ---

from django.shortcuts import render
from .models import Produto, Cliente  # Ajuste conforme seus nomes de modelos

def dashboard_view(request):
    # 1. Total de itens em estoque (Soma de todas as quantidades)
    # Se quiser apenas o número de produtos diferentes, use Produto.objects.count()
    total_estoque = Produto.objects.all().count() 

    # 2. Alertas de Baixo Estoque
    # Filtra produtos onde a quantidade atual é menor ou igual ao mínimo definido
    alertas_baixo_estoque = Produto.objects.filter(quantidade__lte=F('estoque_minimo')).count()

    # 3. Clientes Ativos
    total_clientes_ativos = Cliente.objects.filter(ativo=True).count()

    # 4. Dados Adicionais (Ex: Novos clientes hoje)
    from django.utils import timezone
    hoje = timezone.now().date()
    novos_clientes_hoje = Cliente.objects.filter(data_cadastro__date=hoje).count()

    context = {
        'total_estoque': total_estoque,
        'alertas_baixo_estoque': alertas_baixo_estoque,
        'total_clientes_ativos': total_clientes_ativos,
        'novos_clientes_hoje': novos_clientes_hoje,
        'loja_status': "Online",  # Pode ser dinâmico baseado em alguma lógica
    }

    return render(request, 'dashboard.html', context)

@login_required
def home(request):
    if not hasattr(request.user, 'perfil'):
        return render(request, 'erro.html', {'msg': 'Seu usuário não possui um perfil configurado.'})
    
    perfil = request.user.perfil
    
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
    # Agrupa pedidos por dia e soma o faturamento
    dados_vendas = (
        Pedido.objects.filter(pago=True)
        .annotate(dia=TruncDay('data_pedido'))
        .values('dia')
        .annotate(total_dia=Sum('total'))
        .order_by('dia')
    )

    # Prepara listas para o Chart.js
    labels = [d['dia'].strftime('%d/%m') for d in dados_vendas]
    valores = [float(d['total_dia']) for d in dados_vendas]

    return render(request, 'admin_stats.html', {
        'labels': json.dumps(labels),
        'valores': json.dumps(valores),
    })
    
# --- ESTOQUE E PRODUTOS ---

@login_required
def lista_estoque(request):
    # Base da query (filtrada pelo usuário logado)
    produtos = Produto.objects.filter(loja__vendedor__usuario=request.user)
    
    # Filtro de estoque baixo (opcional, se você já usa)
    if request.GET.get('baixo_estoque'):
        produtos = produtos.filter(estoque__lte=F('estoque_minimo'))

    # Cálculos de Agregação
    totais = produtos.aggregate(
        total_itens=Count('id'),
        valor_estoque=Sum(F('preco') * F('estoque'))
    )

    context = {
        'produtos': produtos,
        'total_itens': totais['total_itens'] or 0,
        'valor_estoque': totais['valor_estoque'] or 0,
    }
    return render(request, 'estoque_lista.html', context)

class ListaEstoqueView(ListView):
    model = Produto
    template_name = 'estoque.html'

    def get_queryset(self):
        vendedor = Vendedor.objects.get(usuario=self.request.user)
        return Produto.objects.filter(loja__vendedor=vendedor)

def vitrine_produtos(request):
    produtos = Produto.objects.filter(quantidade__gt=0)
    
    return render(request, 'vitrine.html', {'produtos': produtos})

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
    
    # IMPORTANTE: Retornar o template se o método for GET para evitar o ValueError de 'None'
    return render(request, 'categoria_form.html')

def cadastrar_produto(request):
    if hasattr(request.user, 'perfil'):
        perfil = request.user.perfil
    if not perfil.loja:
        print("DEBUG: O sistema não encontrou uma loja neste perfil!")
        return redirect('criar_loja')
    categorias = Categoria.objects.all()

    if request.method == "POST":
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao', '')
        categoria_id = request.POST.get('categoria')
        
        estoque_raw = request.POST.get('estoque', '0')
        estoque = int(estoque_raw) if estoque_raw.isdigit() else 0
        
        estoque_min_raw = request.POST.get('estoque_minimo', '5')
        estoque_minimo = int(estoque_min_raw) if estoque_min_raw.isdigit() else 5

        preco_raw = request.POST.get('preco', '0,00')
        try:
            preco_limpo = preco_raw.replace('R$', '').replace('.', '').replace(',', '.').strip()
            preco_final = Decimal(preco_limpo)
        except:
            preco_final = Decimal('0.00')

        try:
            # A mágica acontece aqui: usamos a loja que já está no perfil do usuário
            loja_vinculada = perfil.loja
            categoria_instancia = Categoria.objects.filter(id=categoria_id).first()

            Produto.objects.create(
                loja=loja_vinculada,
                categoria=categoria_instancia,
                nome=nome,
                descricao=descricao,
                preco=preco_final,
                estoque=estoque,
                estoque_minimo=estoque_minimo
            )
            return redirect('lista_estoque')
            
        except Exception as e:
            print(f"Erro ao salvar produto: {e}")
            # Você pode enviar uma mensagem de erro para o template aqui

    return render(request, 'produto_form.html', {'categorias': categorias})

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
def excluir_produto(request, produto_id):
    # Busca o produto garantindo que ele pertença à loja do usuário
    produto = get_object_or_404(Produto, id=produto_id, loja__vendedor__usuario=request.user)
    
    if request.method == 'POST':
        produto.delete()
        return redirect('lista_estoque')
        
    return render(request, 'confirmar_exclusao_produto.html', {'produto': produto})

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
        'total': total_geral
    })
    
def remover_do_carrinho(request, produto_id):
    cart = Cart(request)
    cart.remove(produto_id)
    return redirect('ver_carrinho')

@transaction.atomic
def finalizar_pedido(request):
    cart = Cart(request)
    if not cart.cart:
        return redirect('vitrine_produtos')

    # 1. Recupera o perfil do Cliente logado
    cliente = request.user.perfil_cliente

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
        produto.quantidade -= dados['quantidade']
        produto.save()

    # 4. Limpa o carrinho
    request.session['cart'] = {}
    
    # 5. Processamento de E-mail e PDF (Protegido por try/except)
    try:
        # Gera o HTML do PDF
        html_string = render_to_string('dashboard/pdf_pedido.html', {'pedido': pedido})
        # Gera o PDF em memória
        pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

        # Monta o e-mail
        assunto = f"Nexus Hub - Pedido #{pedido.id} Confirmado!"
        corpo = f"Olá {pedido.cliente.usuario.username}, seu pedido foi recebido com sucesso. O comprovante está em anexo."
        destinatario = [pedido.cliente.usuario.email]

        email = EmailMessage(assunto, corpo, settings.EMAIL_HOST_USER, destinatario)
        email.attach(f'pedido_{pedido.id}.pdf', pdf_file, 'application/pdf')
        email.send()
        
    except Exception as e:
        print(f"Aviso: Não foi possível gerar/enviar o PDF/E-mail. Erro: {e}")
        
    # 6. Notificação para o Administrador
    try:
        assunto_admin = f"🚨 NOVO PEDIDO: #{pedido.id}"
        mensagem_admin = f"""
        Um novo pedido foi finalizado no Nexus Hub!
        Cliente: {pedido.cliente.usuario.username}
        Valor Total: R$ {pedido.total}
        Data: {pedido.data_pedido.strftime('%d/%m/%Y %H:%M')}

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
    
    return render(request, 'pedido_confirmado.html', {'pedido': pedido})

@login_required
def detalhe_pedido(request, pedido_id):
    # Busca o pedido ou retorna 404 se não existir
    # Filtramos pelo cliente logado por segurança
    pedido = get_object_or_404(Pedido, id=pedido_id, cliente=request.user.perfil_cliente)
    
    itens = pedido.itens.all()
    
    return render(request, 'detalhe_pedido.html', {
        'pedido': pedido,
        'itens': itens
    })
    
@login_required
def historico_pedidos(request):
    # Busca todos os pedidos vinculados ao perfil_cliente do usuário logado
    # .order_by('-data_pedido') garante que o mais recente apareça primeiro
    pedidos = Pedido.objects.filter(
        cliente=request.user.perfil_cliente
    ).order_by('-data_pedido')
    
    return render(request, 'historico.html', {'pedidos': pedidos})

def exportar_pedido_pdf(request, pedido_id):
    # 1. Busca os dados
    pedido = get_object_or_404(Pedido, id=pedido_id, cliente=request.user.perfil_cliente)
    
    # 2. Renderiza o HTML para uma string
    html_string = render_to_string('dashboard/pdf_pedido.html', {'pedido': pedido})
    
    # 3. Cria o PDF
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    result = html.write_pdf()

    # 4. Prepara a resposta do navegador
    response = HttpResponse(result, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="pedido_{pedido.id}.pdf"'
    
    return response

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
    
    return render(request, 'editar_loja.html', {'form': form, 'titulo': 'Nova Loja'})

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
    
    return render(request, 'editar_loja.html', {'form': form, 'loja': loja, 'titulo': 'Editar Minha Loja'})

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

def lista_funcionarios(request):
    funcionarios = Funcionario.objects.all()
    return render(request, 'lista_funcionarios.html', {'funcionarios': funcionarios})

def editar_funcionario(request, id):
    funcionario = get_object_or_404(Funcionario, id=id)
    
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
    funcionario = get_object_or_404(Funcionario, id=id)
    funcionario.delete()
    # Mensagem de sucesso opcional para feedback ao usuário
    # messages.success(request, f"Funcionário {funcionario.nome} removido com sucesso.")
    return redirect('lista_funcionarios')

@login_required
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
        vendedor=request.user.vendedor,
        produto=produto,
        quantidade=1,
        valor_total=produto.preco
    )
    
    messages.success(request, f"Venda de {produto.nome} realizada com sucesso!")
    return redirect('lista_estoque')
