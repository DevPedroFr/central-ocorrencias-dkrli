import json

from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Ocorrencia, UserProfile, ObservacaoNOC
from . import teams as teams_notif


def _get_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def login_view(request):
    error = None
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if _get_profile(user).must_change_password:
                return redirect('change_password')
            return redirect('home')
        else:
            error = 'Usuário ou senha inválidos.'
    return render(request, 'login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def home(request):
    if _get_profile(request.user).must_change_password:
        return redirect('change_password')
    return render(request, 'home.html')


@login_required
def manual_acionamento(request):
    return render(request, 'manual_acionamento.html')


@login_required
def observacoes_noc(request):
    grupos = [
        {
            'label': '24×7',
            'nome': 'INTEGRAL',
            'cor': 'blue',
            'clientes': [
                {'slug': 'compare-paraty',           'nome': 'Compare / Paraty',            'tags': ['Máquina Virtual', 'Virtualizador']},
                {'slug': 'torra',                    'nome': 'Torra',                       'tags': ['Backup', 'Wazuh', 'Zabbix']},
                {'slug': 'hospital-nipo',            'nome': 'Hospital NIPO',               'tags': ['Infraestrutura', 'Zabbix', 'Grafana']},
                {'slug': 'liz-cmr',                  'nome': 'Liz CMR',                     'tags': ['Link', 'Firewall', 'Analyzer']},
                {'slug': 'dux-nutrition',            'nome': 'DUX Nutrition',               'tags': ['DIO', 'Cabo UTP', 'Cabo Ótico']},
                {'slug': 'billing-group-qualicorp',  'nome': 'Billing Group / Qualicorp',   'tags': ['Virtualizador', 'Storage', 'Firewall']},
                {'slug': 'usina-vista-alegre',       'nome': 'Usina Vista Alegre',           'tags': ['Máquina Virtual', 'Virtualizador']},
                {'slug': 'licks-legal',              'nome': 'Licks Legal',                 'tags': ['Links', 'Switch', 'Wazuh']},
                {'slug': 'veste',                    'nome': 'Veste',                       'tags': ['Servidores', 'Firewall', 'Switch']},
                {'slug': 'puc-campinas',             'nome': 'PUC Campinas',                'tags': ['Link', 'Analyzer', 'Access Point']},
            ],
        },
        {
            'label': '8×5',
            'nome': 'COMERCIAL',
            'cor': 'orange',
            'clientes': [
                {'slug': 'fundacao-lucy-montoro',    'nome': 'Fundação / Lucy Montoro / AME / FMABC / FUABC / HGC / HMC', 'tags': ['Firewall', 'Servidores', 'Link']},
                {'slug': 'diagi',                    'nome': 'Diagi',                       'tags': ['Licenciamento', 'Firewall', 'Zabbix']},
                {'slug': 'kovi',                     'nome': 'Kovi',                        'tags': ['PopProtect', 'DIO', 'Cabo Ótico']},
                {'slug': 'sindifast',                'nome': 'Sindifast',                   'tags': ['Máquina Virtual', 'Link', 'Switch']},
                {'slug': 'ituran',                   'nome': 'Ituran',                      'tags': ['VPN', 'Servidores', 'Zabbix']},
                {'slug': 'prime-energy',             'nome': 'Prime Energy',                'tags': ['Link', 'AP', 'Firewall']},
                {'slug': 'colegio-pioneiro',         'nome': 'Colégio Pioneiro',            'tags': ['PABX', 'Máquina Virtual', 'Antena']},
                {'slug': 'bellanapoli-wbam',         'nome': 'Bellanapoli / WBAM',          'tags': ['Link', 'Firewall', 'Zabbix']},
                {'slug': 'nippon',                   'nome': 'Nippon',                      'tags': ['Firewall', 'Software', 'Zabbix']},
                {'slug': 'evernex-marfrig',          'nome': 'Evernex / Marfrig',           'tags': ['Hardware', 'Servidores', 'Zabbix']},
                {'slug': 'potencial-florestal',      'nome': 'Potencial Florestal',         'tags': ['Link', 'Firewall', 'Zabbix']},
                {'slug': 'gonzalez',                 'nome': 'Gonzalez',                    'tags': ['Firewall', 'Zabbix', 'Grafana']},
                {'slug': 'futon-company',            'nome': 'Futon Company',               'tags': ['Máquina Virtual', 'Software', 'Firewall']},
                {'slug': 'galeazi',                  'nome': 'Galeazi',                     'tags': ['Firewall', 'Zabbix', 'Grafana']},
                {'slug': 'sakura-turismo',           'nome': 'Sakura Turismo',              'tags': ['Software', 'Firewall', 'Analyzer']},
                {'slug': 'cmd-centro-medico',        'nome': 'CMD – Centro Médico Diagnóstico', 'tags': ['Firewall', 'Zabbix', 'Grafana']},
            ],
        },
    ]
    # Anexa contagem de observações em cada cliente
    for grupo in grupos:
        for cliente in grupo['clientes']:
            cliente['total_obs'] = ObservacaoNOC.objects.filter(cliente_slug=cliente['slug']).count()
    recentes = ObservacaoNOC.objects.select_related('criado_por').order_by('-criado_em')[:4]
    return render(request, 'observacoes_noc.html', {'grupos': grupos, 'recentes': recentes})


# Mapa slug → nome (usado pelas views de detalhe)
_CLIENTES = {
    'compare-paraty':           'Compare / Paraty',
    'torra':                    'Torra',
    'hospital-nipo':            'Hospital NIPO',
    'liz-cmr':                  'Liz CMR',
    'dux-nutrition':            'DUX Nutrition',
    'billing-group-qualicorp':  'Billing Group / Qualicorp',
    'usina-vista-alegre':       'Usina Vista Alegre',
    'licks-legal':              'Licks Legal',
    'veste':                    'Veste',
    'puc-campinas':             'PUC Campinas',
    'fundacao-lucy-montoro':    'Fundação / Lucy Montoro / AME / FMABC / FUABC / HGC / HMC',
    'diagi':                    'Diagi',
    'kovi':                     'Kovi',
    'sindifast':                'Sindifast',
    'ituran':                   'Ituran',
    'prime-energy':             'Prime Energy',
    'colegio-pioneiro':         'Colégio Pioneiro',
    'bellanapoli-wbam':         'Bellanapoli / WBAM',
    'nippon':                   'Nippon',
    'evernex-marfrig':          'Evernex / Marfrig',
    'potencial-florestal':      'Potencial Florestal',
    'gonzalez':                 'Gonzalez',
    'futon-company':            'Futon Company',
    'galeazi':                  'Galeazi',
    'sakura-turismo':           'Sakura Turismo',
    'cmd-centro-medico':        'CMD – Centro Médico Diagnóstico',
}


@login_required
def observacoes_cliente(request, slug):
    nome = _CLIENTES.get(slug)
    if nome is None:
        from django.http import Http404
        raise Http404
    observacoes = ObservacaoNOC.objects.filter(cliente_slug=slug).order_by('-criado_em')
    return render(request, 'observacoes_cliente.html', {
        'cliente_slug': slug,
        'cliente_nome': nome,
        'observacoes': observacoes,
    })


@login_required
@require_POST
def nova_observacao_cliente(request, slug):
    nome = _CLIENTES.get(slug)
    if nome is None:
        from django.http import Http404
        raise Http404
    texto = request.POST.get('texto', '').strip()
    if texto:
        ObservacaoNOC.objects.create(
            cliente_slug=slug,
            cliente_nome=nome,
            texto=texto,
            criado_por=request.user,
        )
    return redirect('observacoes_cliente', slug=slug)


@login_required
@require_POST
def deletar_observacao_cliente(request, pk):
    obs = get_object_or_404(ObservacaoNOC, pk=pk)
    slug = obs.cliente_slug
    obs.delete()
    return redirect('observacoes_cliente', slug=slug)


@login_required
def dashboard(request):
    if _get_profile(request.user).must_change_password:
        return redirect('change_password')
    ocorrencias_abertas = Ocorrencia.objects.filter(status='aberta').order_by('-criado_em')
    ocorrencias_fechadas = Ocorrencia.objects.filter(status='fechada').order_by('-fechado_em')[:20]
    return render(request, 'dashboard.html', {
        'ocorrencias_abertas': ocorrencias_abertas,
        'ocorrencias_fechadas': ocorrencias_fechadas,
    })


@login_required
def change_password(request):
    profile = _get_profile(request.user)
    if not profile.must_change_password:
        return redirect('home')

    error = None
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if not new_password or not confirm_password:
            error = 'Preencha todos os campos.'
        elif new_password != confirm_password:
            error = 'As senhas não coincidem.'
        elif len(new_password) < 6:
            error = 'A senha deve ter pelo menos 6 caracteres.'
        elif new_password == 'mudar@dkrli':
            error = 'Você deve definir uma senha diferente da senha padrão.'
        else:
            request.user.set_password(new_password)
            request.user.save()
            profile.must_change_password = False
            profile.save()
            update_session_auth_hash(request, request.user)
            return redirect('home')

    return render(request, 'change_password.html', {'error': error})


@login_required
def usuarios(request):
    if not request.user.is_superuser:
        return redirect('home')
    users = User.objects.all().order_by('username').prefetch_related('profile')
    users_data = []
    for u in users:
        profile = _get_profile(u)
        users_data.append({
            'id': u.id,
            'username': u.username,
            'is_superuser': u.is_superuser,
            'must_change_password': profile.must_change_password,
            'last_login': u.last_login,
        })
    return render(request, 'users.html', {'users_data': users_data})


@login_required
@require_POST
def alterar_senha_usuario(request, user_id):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Sem permissão'}, status=403)
    target = get_object_or_404(User, pk=user_id)
    new_password = request.POST.get('password', '').strip()
    if not new_password or len(new_password) < 6:
        return JsonResponse({'error': 'Senha inválida (mínimo 6 caracteres).'}, status=400)
    target.set_password(new_password)
    target.save()
    profile = _get_profile(target)
    profile.must_change_password = True
    profile.save()
    return JsonResponse({'status': 'ok', 'username': target.username})


@login_required
@require_POST
def nova_ocorrencia(request):
    if _get_profile(request.user).must_change_password:
        return redirect('change_password')
    titulo = request.POST.get('titulo', '').strip()
    descricao = request.POST.get('descricao', '').strip()
    local = request.POST.get('local', '').strip()
    if titulo and descricao and local:
        occ = Ocorrencia.objects.create(
            titulo=titulo,
            descricao=descricao,
            local=local,
            criado_por=request.user,
        )
        dashboard_url = request.build_absolute_uri('/')
        teams_notif.notificar_abertura(occ, dashboard_url)
    return redirect('dashboard')


@login_required
@require_POST
def notificar_teams(request, pk):
    occ = get_object_or_404(Ocorrencia, pk=pk, status='aberta')
    elapsed = int((timezone.now() - occ.criado_em).total_seconds())
    dashboard_url = request.build_absolute_uri('/')
    teams_notif.notificar_verificacao(occ, elapsed, dashboard_url)
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def confirmar_ocorrencia(request, pk):
    ocorrencia = get_object_or_404(Ocorrencia, pk=pk, status='aberta')
    ocorrencia.ultima_confirmacao = timezone.now()
    ocorrencia.save(update_fields=['ultima_confirmacao'])
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def fechar_ocorrencia(request, pk):
    ocorrencia = get_object_or_404(Ocorrencia, pk=pk, status='aberta')
    try:
        data = json.loads(request.body)
        comentario = data.get('comentario', '').strip()
    except (json.JSONDecodeError, AttributeError):
        comentario = ''
    if not comentario:
        return JsonResponse({'error': 'Comentário de resolução é obrigatório.'}, status=400)
    ocorrencia.status = 'fechada'
    ocorrencia.fechado_em = timezone.now()
    ocorrencia.comentario_fechamento = comentario
    ocorrencia.save(update_fields=['status', 'fechado_em', 'comentario_fechamento'])
    elapsed = int((ocorrencia.fechado_em - ocorrencia.criado_em).total_seconds())
    ocorrencia._fechado_por_username = request.user.username
    dashboard_url = request.build_absolute_uri('/')
    teams_notif.notificar_fechamento(ocorrencia, elapsed, dashboard_url)
    return JsonResponse({'status': 'fechada'})


@login_required
def analytics(request):
    today = timezone.now().date()
    last_7 = [today - timedelta(days=i) for i in range(6, -1, -1)]

    total_abertas = Ocorrencia.objects.filter(status='aberta').count()
    total_fechadas = Ocorrencia.objects.filter(status='fechada').count()

    closed_qs = list(
        Ocorrencia.objects.filter(status='fechada', fechado_em__isnull=False)
    )

    # Overall average resolution time (seconds)
    avg_total_secs = None
    if closed_qs:
        avg_total_secs = (
            sum((o.fechado_em - o.criado_em).total_seconds() for o in closed_qs)
            / len(closed_qs)
        )

    def fmt_duration(secs):
        if secs is None:
            return '—'
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        if h:
            return f'{h}h {m}min'
        return f'{m}min'

    # Per-day average resolution time for last 7 days (in minutes, null = no data)
    day_labels = []
    day_avg_minutes = []
    for day in last_7:
        day_closed = [o for o in closed_qs if o.fechado_em.date() == day]
        day_labels.append(day.strftime('%d/%m'))
        if day_closed:
            avg_mins = (
                sum((o.fechado_em - o.criado_em).total_seconds() for o in day_closed)
                / len(day_closed) / 60
            )
            day_avg_minutes.append(round(avg_mins, 1))
        else:
            day_avg_minutes.append(None)

    return render(request, 'analytics.html', {
        'total_abertas': total_abertas,
        'total_fechadas': total_fechadas,
        'avg_formatted': fmt_duration(avg_total_secs),
        'donut_data': json.dumps([total_abertas, total_fechadas]),
        'day_labels': json.dumps(day_labels),
        'day_avg_minutes': json.dumps(day_avg_minutes),
    })


