from django.shortcuts import render

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
        ]
    }
    return render(request, "dashboard.html", data)