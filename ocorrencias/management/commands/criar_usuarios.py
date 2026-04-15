from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ocorrencias.models import UserProfile

USUARIOS = [
    {'username': 'pedro.franca',       'superuser': True},
    {'username': 'maria.fernanda',     'superuser': False},
    {'username': 'ryan.silva',         'superuser': False},
    {'username': 'andre.alves',        'superuser': False},
    {'username': 'allan.victor',       'superuser': True},
    {'username': 'willston.barbosa',   'superuser': True},
    {'username': 'mmattei',            'superuser': True},
    {'username': 'claudio.luiz',       'superuser': False},
    {'username': 'thiago.proenca',     'superuser': False},
    {'username': 'wellington.barbosa', 'superuser': False},
]

DEFAULT_PASSWORD = 'mudar@dkrli'


class Command(BaseCommand):
    help = 'Cria os usuários iniciais do sistema DKRLI'

    def handle(self, *args, **kwargs):
        # Garante que o admin existente não seja forçado a trocar senha
        for adm_name in ('admin',):
            try:
                adm = User.objects.get(username=adm_name)
                profile, _ = UserProfile.objects.get_or_create(user=adm)
                if profile.must_change_password:
                    profile.must_change_password = False
                    profile.save()
                    self.stdout.write(f'  {adm_name}: perfil atualizado (sem troca forçada)')
            except User.DoesNotExist:
                pass

        for u in USUARIOS:
            user, created = User.objects.get_or_create(username=u['username'])
            if created:
                user.set_password(DEFAULT_PASSWORD)
                user.is_staff = u['superuser']
                user.is_superuser = u['superuser']
                user.save()
                UserProfile.objects.create(user=user, must_change_password=True)
                tipo = 'superadmin' if u['superuser'] else 'usuário'
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ {u["username"]} criado ({tipo}) — senha padrão definida'
                ))
            else:
                self.stdout.write(f'  ~ {u["username"]} já existe, ignorado')

        self.stdout.write(self.style.SUCCESS('\nUsuários criados com sucesso!'))
        self.stdout.write(f'Senha padrão: {DEFAULT_PASSWORD}')
        self.stdout.write('Os usuários deverão trocar a senha no primeiro login.\n')
