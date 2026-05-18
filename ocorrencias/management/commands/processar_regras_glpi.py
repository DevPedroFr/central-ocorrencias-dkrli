import time

from django.core.management.base import BaseCommand

from ocorrencias.glpi import GLPIError, process_active_rules


class Command(BaseCommand):
    help = 'Processa regras de resposta automática do GLPI.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true', help='Executa continuamente em loop.')
        parser.add_argument('--interval', type=int, default=60, help='Intervalo em segundos entre execuções.')
        parser.add_argument('--limit', type=int, default=100, help='Quantidade de problemas recentes consultados.')

    def handle(self, *args, **options):
        loop = options['loop']
        interval = options['interval']
        limit = options['limit']

        while True:
            try:
                summary = process_active_rules(limit=limit)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"regras={summary['rules']} | matches={summary['matched_problems']} | execucoes_ok={summary['executed']}"
                    )
                )
                for error in summary['errors']:
                    self.stdout.write(self.style.WARNING(error))
            except GLPIError as exc:
                self.stdout.write(self.style.ERROR(str(exc)))

            if not loop:
                break
            time.sleep(interval)