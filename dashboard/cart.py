class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('cart')
        if not cart:
            cart = self.session['cart'] = {}
        self.cart = cart

    def add(self, produto_id, quantidade=1):
        p_id = str(produto_id)
        if p_id not in self.cart:
            self.cart[p_id] = {'quantidade': 0}
        self.cart[p_id]['quantidade'] += quantidade
        self.save()

    def save(self):
        self.session.modified = True

    def remove(self, produto_id):
        p_id = str(produto_id)
        if p_id in self.cart:
            del self.cart[p_id]
            self.save()