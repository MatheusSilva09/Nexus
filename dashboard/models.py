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
    # Relacionamento com User (usuario_id)
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_cliente')
    telefone = models.CharField(max_length=20)
    endereco = models.TextField()
    
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
    
    # Validação nativa do Django para e-mails
    email = models.EmailField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="E-mail"
    )
    
    # TextField para suportar endereços longos e o textarea do formulário
    endereco = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Endereço / Complemento"
    )
    
    # Campo de controle interno (Útil para a listagem)
    data_cadastro = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Data de Cadastro"
    )
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['-data_cadastro'] # Mais recentes primeiro

    def __str__(self):
        return self.nome

    def __str__(self):
        return self.usuario.username
    
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

    def __str__(self):
        return self.nome

class ProdutoImagem(models.Model):
    produto = models.ForeignKey(Produto, related_name='imagens', on_delete=models.CASCADE)
    imagem = models.ImageField(upload_to='produtos/')

# --- CARRINHO E PEDIDOS ---

class Carrinho(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    data_criacao = models.DateTimeField(auto_now_add=True)

class ItemCarrinho(models.Model):
    carrinho = models.ForeignKey(Carrinho, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField(default=1)

class Pedido(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    data_criacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='Aguardando Pagamento')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    pago = models.BooleanField(default=False)

class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, related_name='itens', on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade = models.PositiveIntegerField(default=1)

class Pagamento(models.Model):
    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE)
    metodo = models.CharField(max_length=50) # Ex: Pix, Cartão
    status = models.CharField(max_length=50)
    id_transacao = models.CharField(max_length=255)


# --- VENDAS ---

class Venda(models.Model):
    vendedor = models.ForeignKey(User, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True)
    quantidade = models.IntegerField()
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Venda {self.id} - {self.vendedor.nome_exibicao}"

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