from decimal import Decimal
from .models import Produto  # Certifique-se de ajustar o import para o seu app de produtos

class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('cart')
        if not cart:
            cart = self.session['cart'] = {}
        self.cart = cart

    def add(self, produto_id, quantidade=1):
        p_id = str(produto_id)
        
        # 1. Garante que o item existe e é um dicionário antes de somar
        if p_id not in self.cart:
            self.cart[p_id] = {'quantidade': 0}
        
        # 2. Segurança: Certifique-se de que o que está na posição é um dicionário
        if isinstance(self.cart[p_id], dict):
            self.cart[p_id]['quantidade'] += quantidade
        else:
            # Se por algum erro o dado estiver corrompido, reseta
            self.cart[p_id] = {'quantidade': quantidade}
            
        self.save()

    def save(self):
        self.session['carrinho'] = self.cart
        self.session.modified = True

    def remove(self, produto_id):
        p_id = str(produto_id)
        if p_id in self.cart:
            del self.cart[p_id]
            self.save()

    def __iter__(self):
        """
        Itera sobre os itens do carrinho, buscando os produtos atualizados do banco 
        e aplicando a regra de preço promocional/desconto dinamicamente.
        """
        produto_ids = self.cart.keys()
        produtos = Produto.objects.filter(id__in=produto_ids)
        
        cart_copy = self.cart.copy()
        for produto in produtos:
            cart_copy[str(produto.id)]['produto'] = produto

        for item in cart_copy.values():
            # Define o preço dinâmico validando a promoção ativa
            if item['produto'].em_oferta and item['produto'].preco_promocional:
                item['preco'] = Decimal(str(item['produto'].preco_promocional))
            else:
                item['preco'] = Decimal(str(item['produto'].preco))
            
            item['subtotal'] = item['preco'] * item['quantidade']
            yield item

    def __len__(self):
        """
        Retorna a quantidade total de itens no carrinho (útil para badges no menu).
        """
        return sum(item['quantidade'] for item in self.cart.values())

    def get_total_price(self):
        """
        Calcula o valor total geral do carrinho já abatendo todas as promoções.
        """
        total = Decimal('0.00')
        produto_ids = self.cart.keys()
        produtos = Produto.objects.filter(id__in=produto_ids)
        
        for produto in produtos:
            quantidade = self.cart[str(produto.id)]['quantidade']
            if produto.em_oferta and produto.preco_promocional:
                preco_final = Decimal(str(produto.preco_promocional))
            else:
                preco_final = Decimal(str(produto.preco))
            
            total += preco_final * quantidade
        return total

    def clear(self):
        """
        Esvazia o carrinho de compras da sessão após o pedido ser finalizado.
        """
        del self.session['cart']
        self.save()