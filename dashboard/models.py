from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

# --- CORE E PERFIS ---

class Vendedor(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendedor_perfil')
    aprovado = models.BooleanField(default=False)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario.username} - {'Aprovado' if self.aprovado else 'Pendente'}"

class Loja(models.Model):
    # FK fiel ao dicionário: Relacionamento com vendedor
    vendedor = models.ForeignKey(Vendedor, on_delete=models.CASCADE, related_name='lojas') 
    nome = models.CharField(max_length=255) # String
    descricao = models.TextField() 

    def __str__(self):
        return self.nome

class Cliente(models.Model):
    # ALTERAÇÃO CRITICA: ForeignKey permite que UM usuário cadastre VÁRIOS clientes
    usuario = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='clientes'
    )
    
    nome = models.CharField(
        max_length=150, 
        verbose_name="Nome Completo"
    )
    
    telefone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name="Telefone / WhatsApp"
    )
    
    email = models.EmailField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="E-mail"
    )
    
    endereco = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Endereço / Complemento"
    )
    
    data_cadastro = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Data de Cadastro"
    )
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['-data_cadastro'] # Mais recentes primeiro
    
class Perfil(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil')
    NIVEL_ACESSO = (
        ('ADMIN', 'Nexus Hub'),    # Você (Dono do Sistema/Suporte)
        ('DONO', 'Dono da Loja'),   # O cara que criou a empresa
        ('GERENTE', 'Gerente'),     # O funcionário com acesso quase total
        ('CLIENTE', 'Cliente'),     # Quem compra na loja
    )
    nivel = models.CharField(max_length=10, choices=NIVEL_ACESSO, default='CLIENTE')
    loja = models.ForeignKey(Loja, on_delete=models.SET_NULL, null=True, blank=True, related_name='membros')

    def __str__(self):
        return f"{self.usuario.username} - {self.nivel}"
    
class Funcionario(models.Model):
    usuario_id = models.ForeignKey(User, on_delete=models.CASCADE, related_name='equipe')
    nome = models.CharField(max_length=150)
    cargo = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True)
    data_admissao = models.DateField(auto_now_add=True) # Adiciona a data de hoje automaticamente

    def __str__(self):
        return f"{self.nome} - {self.cargo}"
    
# --- PRODUTOS E CATEGORIAS ---

class Categoria(models.Model):
    nome = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)

class Produto(models.Model):
    loja = models.ForeignKey(Loja, on_delete=models.CASCADE)
    categoria = models.ForeignKey('Categoria', on_delete=models.SET_NULL, null=True, blank=True)
    nome = models.CharField(max_length=255)
    descricao = models.TextField()
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    estoque = models.IntegerField(default=0)
    estoque_minimo = models.IntegerField(default=5)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    em_oferta = models.BooleanField(default=False, verbose_name="Ativar Promoção?")
    preco_promocional = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name="Preço com Desconto"
    )
    
    @property
    def status_estoque(self):
        if self.estoque > self.estoque_minimo:
            return "À Venda"
        elif 0 < self.estoque <= self.estoque_minimo:
            return "Estoque Baixo"
        elif self.estoque <= 0:
            return "Sem Estoque"
        return "Pendente"

    def diminuir_estoque(self, qtd):
        if self.estoque >= qtd:
            self.estoque -= qtd
            self.save()
        else:
            raise ValueError("Estoque insuficiente!")

    def precisa_repor(self):
        return self.estoque <= self.estoque_minimo
    
    def preco_final(self):
        if self.em_oferta and self.preco_promocional:
            return self.preco_promocional
        return self.preco

    def __str__(self):
        return self.nome

class ProdutoImagem(models.Model):
    produto = models.ForeignKey(Produto, related_name='imagens', on_delete=models.CASCADE)
    imagem = models.ImageField(upload_to='produtos/galeria/')
    ordem = models.IntegerField(default=0)

    class Meta:
        db_table = 'dashboard_produtoimagem' # Troque pelo nome real se houver
        ordering = ['ordem', 'id']

# --- CARRINHO E PEDIDOS ---

class Carrinho(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Carrinho"
        verbose_name_plural = "Carrinhos"

    def __str__(self):
        return f"Carrinho de {self.cliente.nome} - {self.data_criacao.strftime('%d/%m/%Y')}"

    @property
    def total_carrinho(self):
        # Soma todos os subtotais dos itens vinculados a este carrinho
        return sum(item.subtotal for item in self.itens.all())


class ItemCarrinho(models.Model):
    carrinho = models.ForeignKey(Carrinho, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField(default=1)

    @property
    def subtotal(self):
        # Validação automática da oferta ativa para calcular o subtotal no banco/sessão
        preco_final = self.produto.preco_promocional if (self.produto.em_oferta and self.produto.preco_promocional) else self.produto.preco
        return preco_final * self.quantidade

    def __str__(self):
        return f"{self.quantidade}x {self.produto.nome} no Carrinho"


class Pedido(models.Model):
    STATUS_CHOICES = [
        ('Aguardando Pagamento', 'Aguardando Pagamento'),
        ('Pago', 'Pago'),
        ('Enviado', 'Enviado'),
        ('Cancelado', 'Cancelado'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    data_criacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Aguardando Pagamento')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    pago = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-data_criacao'] # Traz sempre os pedidos mais recentes primeiro

    def __str__(self):
        return f"Pedido #{self.id} - {self.cliente.nome}"


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, related_name='itens', on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    preco = models.DecimalField(max_digits=10, decimal_places=2) # Mantém o histórico real da venda
    quantidade = models.PositiveIntegerField(default=1)

    @property
    def subtotal(self):
        return self.preco * self.quantidade

    def __str__(self):
        return f"{self.quantidade}x {self.produto.nome} (Pedido #{self.pedido.id})"


class Pagamento(models.Model):
    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE)
    metodo = models.CharField(max_length=50) # Ex: Pix, Cartão
    status = models.CharField(max_length=50)
    id_transacao = models.CharField(max_length=255)

    def __str__(self):
        return f"Pagamento do Pedido #{self.pedido.id} - Status: {self.status}"


# --- VENDAS ---

class Venda(models.Model):
    vendedor = models.ForeignKey(User, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True)
    quantidade = models.IntegerField()
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Venda {self.id} - {self.vendedor.username}"

@receiver(post_save, sender=User)    
def create_vendedor_perfil(sender, instance, created, **kwargs):
    """
    Sempre que um novo User for criado, criamos automaticamente 
    um perfil de Vendedor pendente de aprovação.
    """
    if created:
        Vendedor.objects.create(usuario=instance)
    
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # USE 'usuario' em vez de 'user'
        Perfil.objects.create(usuario=instance)
