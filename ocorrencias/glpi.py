import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request

from datetime import datetime
from pathlib import Path

from django.utils import timezone

from .models import AutoResponseExecution, AutoResponseRule


def _load_local_env():
    env_path = Path(__file__).resolve().parent.parent / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, value = stripped.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()


GLPI_URL = os.getenv('GLPI_URL', 'https://sd.dkrli.com.br').rstrip('/')
GLPI_APP_TOKEN = os.getenv('GLPI_APP_TOKEN', '')
GLPI_USER_TOKEN = os.getenv('GLPI_USER_TOKEN', '')
OPEN_PROBLEM_STATUSES = [1, 2, 4]


class GLPIError(Exception):
    pass


class GLPIClient:
    def __init__(self, url=None, app_token=None, user_token=None):
        self.url = (url or GLPI_URL).rstrip('/')
        self.app_token = app_token or GLPI_APP_TOKEN
        self.user_token = user_token or GLPI_USER_TOKEN
        self.session_token = None
        self.ssl_context = ssl._create_unverified_context()

    def __enter__(self):
        self.init_session()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.kill_session()

    def configured(self):
        return bool(self.url and self.app_token and self.user_token)

    def init_session(self):
        if not self.configured():
            raise GLPIError('Configuração GLPI ausente. Defina GLPI_URL, GLPI_APP_TOKEN e GLPI_USER_TOKEN.')
        data = self._request(
            'GET',
            '/apirest.php/initSession',
            headers={
                'Authorization': f'user_token {self.user_token}',
            },
            require_session=False,
        )
        self.session_token = data.get('session_token')
        if not self.session_token:
            raise GLPIError('Não foi possível iniciar sessão no GLPI.')
        return self.session_token

    def kill_session(self):
        if not self.session_token:
            return
        try:
            self._request('GET', '/apirest.php/killSession')
        except GLPIError:
            pass
        finally:
            self.session_token = None

    def _request(self, method, path, params=None, payload=None, headers=None, require_session=True):
        full_url = f'{self.url}{path}'
        if params:
            query = urllib.parse.urlencode(params)
            full_url = f'{full_url}?{query}'
        base_headers = {
            'Content-Type': 'application/json',
            'App-Token': self.app_token,
        }
        if require_session:
            if not self.session_token:
                raise GLPIError('Sessão GLPI não iniciada.')
            base_headers['Session-Token'] = self.session_token
        if headers:
            base_headers.update(headers)
        data = None
        if payload is not None:
            data = json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(full_url, data=data, headers=base_headers, method=method)
        try:
            with urllib.request.urlopen(request, context=self.ssl_context, timeout=20) as response:
                raw = response.read().decode('utf-8')
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode('utf-8')
            except Exception:
                detail = str(exc)
            raise GLPIError(f'GLPI {exc.code}: {detail}') from exc
        except urllib.error.URLError as exc:
            raise GLPIError(f'Falha de conexão com GLPI: {exc.reason}') from exc

    def get_recent_problems(self, limit=10, statuses=None):
        statuses = statuses or OPEN_PROBLEM_STATUSES
        collected = []
        offset = 0
        page_size = max(limit, 30)
        while len(collected) < limit:
            page = self._request(
                'GET',
                '/apirest.php/Problem',
                params={
                    'range': f'{offset}-{offset + page_size - 1}',
                    'expand_dropdowns': False,
                    'order': 'DESC',
                    'sort': 'date',
                },
            )
            if not page:
                break
            page_items = [item for item in page if item.get('status') in statuses]
            collected.extend(page_items)
            if len(page) < page_size:
                break
            offset += page_size
        return collected[:limit]

    def get_problem(self, problem_id):
        return self._request(
            'GET',
            f'/apirest.php/Problem/{problem_id}',
            params={'expand_dropdowns': True, 'get_hateoas': False},
        )

    def find_user_by_name(self, analyst_name):
        normalized = (analyst_name or '').strip()
        if not normalized:
            raise GLPIError('Nome do analista não informado.')
        payload = self._request(
            'GET',
            '/apirest.php/search/User',
            params={
                'criteria[0][field]': 1,
                'criteria[0][searchtype]': 'contains',
                'criteria[0][value]': normalized,
                'forcedisplay[0]': 1,
                'forcedisplay[1]': 2,
                'range': '0-49',
            },
        )
        rows = payload.get('data') or []
        if not rows:
            raise GLPIError(f'Nenhum usuário GLPI encontrado para "{normalized}".')

        exact_matches = []
        contains_matches = []
        needle = normalized.casefold()
        for row in rows:
            login = str(row.get('1') or '').strip()
            user_id = row.get('2')
            if not login or not user_id:
                continue
            if login.casefold() == needle:
                exact_matches.append({'id': int(user_id), 'login': login})
            elif needle in login.casefold():
                contains_matches.append({'id': int(user_id), 'login': login})

        matches = exact_matches or contains_matches
        if not matches:
            raise GLPIError(f'Nenhum usuário GLPI utilizável encontrado para "{normalized}".')
        if len(matches) > 1:
            names = ', '.join(match['login'] for match in matches[:5])
            raise GLPIError(f'Nome de analista ambíguo: "{normalized}". Correspondências: {names}')
        return matches[0]

    def assign_problem(self, problem_id, glpi_user_id):
        attempts = [
            (
                f'/apirest.php/Problem/{problem_id}/Problem_User',
                {'input': {'users_id': int(glpi_user_id), 'type': 2}},
            ),
            (
                '/apirest.php/Problem_User',
                {'input': {'problems_id': int(problem_id), 'users_id': int(glpi_user_id), 'type': 2}},
            ),
        ]
        last_error = None
        for path, payload in attempts:
            try:
                return self._request('POST', path, payload=payload)
            except GLPIError as exc:
                last_error = exc
        raise GLPIError(str(last_error or 'Falha ao atribuir problema no GLPI.'))

    def add_problem_followup(self, problem_id, content):
        attempts = [
            (
                f'/apirest.php/Problem/{problem_id}/ITILFollowup',
                {'input': {'content': content, 'is_private': 0}},
            ),
            (
                '/apirest.php/ITILFollowup',
                {'input': {'itemtype': 'Problem', 'items_id': int(problem_id), 'content': content, 'is_private': 0}},
            ),
        ]
        last_error = None
        for path, payload in attempts:
            try:
                return self._request('POST', path, payload=payload)
            except GLPIError as exc:
                last_error = exc
        raise GLPIError(str(last_error or 'Falha ao incluir followup no GLPI.'))


def parse_glpi_datetime(value):
    if not value:
        return None
    try:
        naive = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        return timezone.make_aware(naive, timezone.get_current_timezone())
    except ValueError:
        return None


def process_active_rules(limit=100):
    summary = {
        'rules': 0,
        'matched_problems': 0,
        'executed': 0,
        'errors': [],
    }
    active_rules = list(
        AutoResponseRule.objects.filter(enabled=True, active_until__gte=timezone.now()).select_related('created_by')
    )
    summary['rules'] = len(active_rules)
    if not active_rules:
        return summary

    with GLPIClient() as client:
        recent_problems = client.get_recent_problems(limit=limit)
        problems_by_id = {problem.get('id'): problem for problem in recent_problems}

        for rule in active_rules:
            if not rule.glpi_user_id:
                try:
                    user_match = client.find_user_by_name(rule.analyst_name)
                    rule.glpi_user_id = user_match['id']
                    rule.save(update_fields=['glpi_user_id'])
                except GLPIError as exc:
                    summary['errors'].append(str(exc))
                    continue

            candidate_problems = []
            origin_problem = problems_by_id.get(rule.problem_id_origem)
            if origin_problem is None:
                try:
                    origin_problem = client.get_problem(rule.problem_id_origem)
                except GLPIError:
                    origin_problem = None
            if origin_problem:
                candidate_problems.append(origin_problem)

            for problem in recent_problems:
                if problem.get('name') == rule.problem_title and problem.get('id') != rule.problem_id_origem:
                    created_at = parse_glpi_datetime(problem.get('date_creation') or problem.get('date'))
                    if created_at is None or created_at >= rule.created_at:
                        candidate_problems.append(problem)

            seen_ids = set()
            for problem in candidate_problems:
                problem_id = problem.get('id')
                if not problem_id or problem_id in seen_ids:
                    continue
                seen_ids.add(problem_id)
                summary['matched_problems'] += 1

                execution = AutoResponseExecution.objects.filter(
                    rule=rule,
                    glpi_problem_id=problem_id,
                ).first()
                if execution and execution.assignment_success and execution.followup_success:
                    continue

                assignment_success = execution.assignment_success if execution else False
                followup_success = execution.followup_success if execution else False
                response_payload = {}
                if execution and execution.response_payload:
                    try:
                        response_payload = json.loads(execution.response_payload)
                    except json.JSONDecodeError:
                        response_payload = {'previous_payload': execution.response_payload}

                if not assignment_success:
                    try:
                        assign_result = client.assign_problem(problem_id, rule.glpi_user_id)
                        assignment_success = True
                        response_payload['assignment'] = assign_result
                        response_payload.pop('assignment_error', None)
                    except GLPIError as exc:
                        response_payload['assignment_error'] = str(exc)

                if not followup_success:
                    try:
                        followup_result = client.add_problem_followup(problem_id, rule.followup_text)
                        followup_success = True
                        response_payload['followup'] = followup_result
                        response_payload.pop('followup_error', None)
                    except GLPIError as exc:
                        response_payload['followup_error'] = str(exc)

                if execution is None:
                    execution = AutoResponseExecution.objects.create(
                        rule=rule,
                        glpi_problem_id=problem_id,
                        glpi_problem_title=problem.get('name', rule.problem_title),
                        assignment_success=assignment_success,
                        followup_success=followup_success,
                        response_payload=json.dumps(response_payload, ensure_ascii=False),
                    )
                else:
                    execution.glpi_problem_title = problem.get('name', rule.problem_title)
                    execution.assignment_success = assignment_success
                    execution.followup_success = followup_success
                    execution.response_payload = json.dumps(response_payload, ensure_ascii=False)
                    execution.save(update_fields=[
                        'glpi_problem_title',
                        'assignment_success',
                        'followup_success',
                        'response_payload',
                    ])

                if assignment_success and followup_success:
                    summary['executed'] += 1
                else:
                    summary['errors'].append(
                        f'Problema {problem_id}: atribuição={assignment_success}, followup={followup_success}'
                    )
    return summary