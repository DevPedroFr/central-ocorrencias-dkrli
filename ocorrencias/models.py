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
    comentario_fechamento = models.TextField(null=True, blank=True, verbose_name='Comentário de fechamento')

    class Meta:
        verbose_name = 'Ocorrência'
        verbose_name_plural = 'Ocorrências'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.titulo} ({self.status})'


class AutoResponseRule(models.Model):
    problem_id_origem = models.PositiveIntegerField(verbose_name='Problema de origem no GLPI')
    problem_title = models.CharField(max_length=255, verbose_name='Título do alerta')
    analyst_name = models.CharField(max_length=255, default='', verbose_name='Nome do analista')
    followup_text = models.TextField(verbose_name='Texto de resposta automática')
    active_until = models.DateTimeField(verbose_name='Regra ativa até')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Criado por')
    glpi_user_id = models.PositiveIntegerField(verbose_name='ID do usuário no GLPI')
    enabled = models.BooleanField(default=True, verbose_name='Ativa')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizada em')

    class Meta:
        verbose_name = 'Regra de Resposta Automática'
        verbose_name_plural = 'Regras de Resposta Automática'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.problem_title} -> {self.analyst_name}'


class AutoResponseExecution(models.Model):
    rule = models.ForeignKey(
        AutoResponseRule,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name='Regra',
    )
    glpi_problem_id = models.PositiveIntegerField(verbose_name='ID do problema no GLPI')
    glpi_problem_title = models.CharField(max_length=255, verbose_name='Título do problema')
    assignment_success = models.BooleanField(default=False, verbose_name='Atribuição executada')
    followup_success = models.BooleanField(default=False, verbose_name='Followup executado')
    response_payload = models.TextField(blank=True, default='', verbose_name='Resposta técnica')
    executed_at = models.DateTimeField(auto_now_add=True, verbose_name='Executado em')

    class Meta:
        verbose_name = 'Execução de Resposta Automática'
        verbose_name_plural = 'Execuções de Resposta Automática'
        ordering = ['-executed_at']
        constraints = [
            models.UniqueConstraint(
                fields=['rule', 'glpi_problem_id'],
                name='unique_rule_problem_execution',
            )
        ]

    def __str__(self):
        return f'Regra {self.rule_id} em problema {self.glpi_problem_id}'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    must_change_password = models.BooleanField(default=False, verbose_name='Deve trocar senha')
    glpi_analyst_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Nome do analista no GLPI',
    )
    glpi_user_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='ID do usuário no GLPI',
    )

    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuários'

    def __str__(self):
        return f'Perfil de {self.user.username}'

