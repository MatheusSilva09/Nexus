from django import forms
from .models import Loja, Cliente, Produto

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
        fields = ['nome', 'descricao', 'preco', 'estoque', 'categoria']
        
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Digite o nome do produto...'}),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Descreva seu produto...',
                'rows': 3
            }),
            'preco': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_preco', 'placeholder': 'R$ 0,00'}),
            'estoque': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'categoria': forms.Select(attrs={'class': 'form-control select-nexus'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preco'].localize = True
        self.fields['preco'].widget.is_localized = True