from django.contrib import admin
from .models import Ocorrencia


@admin.register(Ocorrencia)
class OcorrenciaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'local', 'status', 'criado_por', 'criado_em', 'fechado_em')
    list_filter = ('status',)
    search_fields = ('titulo', 'descricao', 'local')
    readonly_fields = ('criado_em', 'ultima_confirmacao', 'fechado_em')

