from django import forms
from .models import Loja, Cliente, Produto
import re
from decimal import Decimal, InvalidOperation
from .models import Produto

class LojaForm(forms.ModelForm):
    class Meta:
        model = Loja
        fields = ['nome', 'descricao']
        
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Digite o nome da loja...'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control', 
                'placeholder': 'Descreva sua loja...',
                'rows': 4
            }),
        }
        
class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nome', 'telefone', 'email', 'endereco']
        widgets = {
            'telefone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(00) 00000-0000',
                'style': 'padding-left: 45px;',
            }),
        }

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ['nome', 'descricao', 'preco', 'estoque', 'estoque_minimo', 'categoria', 'em_oferta', 'preco_promocional'] # Seus campos normais

    def clean_preco(self):
        # Captura o valor exatamente como veio do HTML
        preco_raw = self.cleaned_data.get('preco')
        
        # Se o Django já converteu para Decimal ou veio limpo, apenas retorna
        if isinstance(preco_raw, Decimal):
            return preco_raw
            
        # Caso venha como string do POST com máscaras residuais, limpamos com regex
        preco_string = str(preco_raw)
        preco_limpo = re.sub(r'[^\d.,]', '', preco_string).strip()
        
        if ',' in preco_limpo and '.' in preco_limpo:
            if preco_limpo.rfind('.') < preco_limpo.rfind(','):
                preco_limpo = preco_limpo.replace('.', '')
                
        preco_limpo = preco_limpo.replace(',', '.')
        
        try:
            return Decimal(preco_limpo)
        except (InvalidOperation, ValueError, TypeError):
            return Decimal('0.00')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preco_promocional'].widget.attrs.update({
            'class': 'form-control-nexus',
            'placeholder': 'R$ 0,00'
        })
        self.fields['em_oferta'].widget.attrs.update({
            'class': 'form-check-input-nexus'
        })