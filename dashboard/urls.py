from django.urls import path
from . import views
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def home(request):
    return render(request, "dashboard.html")

urlpatterns = [
    path('', views.home, name='home'),
]