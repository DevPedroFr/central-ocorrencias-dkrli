from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('nova/', views.nova_ocorrencia, name='nova_ocorrencia'),
    path('confirmar/<int:pk>/', views.confirmar_ocorrencia, name='confirmar_ocorrencia'),
    path('fechar/<int:pk>/', views.fechar_ocorrencia, name='fechar_ocorrencia'),
    path('notificar-teams/<int:pk>/', views.notificar_teams, name='notificar_teams'),
    path('trocar-senha/', views.change_password, name='change_password'),
    path('usuarios/', views.usuarios, name='usuarios'),
    path('usuarios/<int:user_id>/alterar-senha/', views.alterar_senha_usuario, name='alterar_senha_usuario'),
]
