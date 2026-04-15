from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Ocorrencia, UserProfile
from . import teams as teams_notif


def _get_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def login_view(request):
    error = None
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if _get_profile(user).must_change_password:
                return redirect('change_password')
            return redirect('dashboard')
        else:
            error = 'Usuário ou senha inválidos.'
    return render(request, 'login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


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
        return redirect('dashboard')

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
            return redirect('dashboard')

    return render(request, 'change_password.html', {'error': error})


@login_required
def usuarios(request):
    if not request.user.is_superuser:
        return redirect('dashboard')
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
    ocorrencia.status = 'fechada'
    ocorrencia.fechado_em = timezone.now()
    ocorrencia.save(update_fields=['status', 'fechado_em'])
    return JsonResponse({'status': 'fechada'})

