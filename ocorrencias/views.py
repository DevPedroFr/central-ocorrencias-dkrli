import json

from datetime import timedelta

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .glpi import GLPIClient, GLPIError
from .models import AutoResponseExecution, AutoResponseRule, Ocorrencia, UserProfile
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
def configuracao_resposta_automatica(request):
    if _get_profile(request.user).must_change_password:
        return redirect('change_password')

    recent_problems = []
    integration_error = None
    try:
        with GLPIClient() as client:
            recent_problems = client.get_recent_problems(limit=10)
    except GLPIError as exc:
        integration_error = str(exc)

    active_rules = AutoResponseRule.objects.filter(
        enabled=True,
        active_until__gte=timezone.now(),
    ).select_related('created_by')

    return render(request, 'auto_response_config.html', {
        'recent_problems': recent_problems,
        'integration_error': integration_error,
        'active_rules': active_rules,
    })


@login_required
def nova_regra_resposta_automatica(request, problem_id):
    if _get_profile(request.user).must_change_password:
        return redirect('change_password')

    try:
        with GLPIClient() as client:
            problem = client.get_problem(problem_id)
    except GLPIError as exc:
        messages.error(request, f'Falha ao consultar problema no GLPI: {exc}')
        return redirect('configuracao_resposta_automatica')

    profile = _get_profile(request.user)

    if request.method == 'POST':
        duration_minutes = request.POST.get('duration_minutes', '').strip()
        followup_text = request.POST.get('followup_text', '').strip()
        analyst_name = request.POST.get('analyst_name', '').strip()

        if not duration_minutes.isdigit() or int(duration_minutes) <= 0:
            messages.error(request, 'Informe um tempo de vigência válido em minutos.')
        elif not followup_text:
            messages.error(request, 'Informe a resposta automática que será enviada ao GLPI.')
        elif not analyst_name:
            messages.error(request, 'Informe o nome do analista para atribuição automática.')
        else:
            try:
                with GLPIClient() as client:
                    user_match = client.find_user_by_name(analyst_name)
            except GLPIError as exc:
                messages.error(request, f'Falha ao localizar analista no GLPI: {exc}')
            else:
                active_until = timezone.now() + timedelta(minutes=int(duration_minutes))
                AutoResponseRule.objects.create(
                    problem_id_origem=problem_id,
                    problem_title=problem.get('name', ''),
                    analyst_name=user_match['login'],
                    followup_text=followup_text,
                    active_until=active_until,
                    created_by=request.user,
                    glpi_user_id=user_match['id'],
                )
                changed_fields = []
                if profile.glpi_user_id != user_match['id']:
                    profile.glpi_user_id = user_match['id']
                    changed_fields.append('glpi_user_id')
                if profile.glpi_analyst_name != user_match['login']:
                    profile.glpi_analyst_name = user_match['login']
                    changed_fields.append('glpi_analyst_name')
                if changed_fields:
                    profile.save(update_fields=changed_fields)
                messages.success(request, 'Regra criada com sucesso.')
                return redirect('configuracao_resposta_automatica')

    return render(request, 'auto_response_rule_form.html', {
        'problem': problem,
        'default_analyst_name': profile.glpi_analyst_name or '',
    })


@login_required
@require_POST
def desativar_regra_resposta_automatica(request, rule_id):
    rule = get_object_or_404(AutoResponseRule, pk=rule_id)
    if not (request.user.is_superuser or rule.created_by_id == request.user.id):
        return JsonResponse({'error': 'Sem permissão.'}, status=403)
    rule.enabled = False
    rule.save(update_fields=['enabled'])
    return redirect('configuracao_resposta_automatica')


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


