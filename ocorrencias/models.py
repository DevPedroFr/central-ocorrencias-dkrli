from django.db import models
from django.contrib.auth.models import User


class Ocorrencia(models.Model):
    STATUS_CHOICES = [
        ('aberta', 'Aberta'),
        ('fechada', 'Fechada'),
    ]

    titulo = models.CharField(max_length=200, verbose_name='Título')
    descricao = models.TextField(verbose_name='Descrição')
    local = models.CharField(max_length=200, verbose_name='Local')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='aberta', verbose_name='Status')
    criado_por = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Registrado por')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    ultima_confirmacao = models.DateTimeField(auto_now_add=True, verbose_name='Última confirmação')
    fechado_em = models.DateTimeField(null=True, blank=True, verbose_name='Fechado em')

    class Meta:
        verbose_name = 'Ocorrência'
        verbose_name_plural = 'Ocorrências'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.titulo} ({self.status})'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    must_change_password = models.BooleanField(default=False, verbose_name='Deve trocar senha')

    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuários'

    def __str__(self):
        return f'Perfil de {self.user.username}'

