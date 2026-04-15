from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def home(request):
    data = {
        "receita": "R$ 4.107,38",
        "vendas": 259,
        "clientes": 12,
        "avisos": 3,
        "produtos": [
            {"nome": "Azeite", "quantidade": 120},
            {"nome": "Café", "quantidade": 98},
            {"nome": "Chá", "quantidade": 75},
        ],
        "user": request.user,
    }
    return render(request, "dashboard.html", data)

@login_required
def profile(request):
    context = {
        'user': request.user,
        'last_login': request.user.last_login,
        'date_joined': request.user.date_joined,
    }
    return render(request, 'registration/profile.html', context)