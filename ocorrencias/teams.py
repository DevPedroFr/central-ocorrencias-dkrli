"""
Utilitário para envio de notificações ao Microsoft Teams via Incoming Webhook.
Usa Adaptive Card com botões de ação (mais próximo de enquete possível via webhook).
"""

import json
import urllib.request
import urllib.error

WEBHOOK_URL = (
    "https://dkrlit.webhook.office.com/webhookb2/"
    "bf1f38e1-11f7-4eba-8311-2b2c8814b256@52c23e61-9938-4915-92ab-d67de408e965/"
    "IncomingWebhook/3db4982712c34475839d3e1841289454/"
    "7f7172e8-8bfe-42ac-af9a-c7fbc15bfb57/"
    "V2mcfPSchQnGKzdkdEiHTbRx9AiIPmpuyN6BLGhQYJ-YE1"
)


def _post(payload: dict) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status == 200
    except Exception:
        return False


def _elapsed_str(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}h {m:02d}min"
    if m:
        return f"{m}min {s:02d}s"
    return f"{s}s"


def notificar_abertura(ocorrencia, dashboard_url: str) -> bool:
    """Envia notificação de nova ocorrência aberta."""
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Container",
                            "style": "attention",
                            "items": [
                                {
                                    "type": "ColumnSet",
                                    "columns": [
                                        {
                                            "type": "Column",
                                            "width": "auto",
                                            "items": [
                                                {
                                                    "type": "TextBlock",
                                                    "text": "🚨",
                                                    "size": "ExtraLarge",
                                                }
                                            ],
                                        },
                                        {
                                            "type": "Column",
                                            "width": "stretch",
                                            "items": [
                                                {
                                                    "type": "TextBlock",
                                                    "text": "Nova Ocorrência Aberta",
                                                    "weight": "Bolder",
                                                    "size": "Large",
                                                    "color": "Attention",
                                                },
                                                {
                                                    "type": "TextBlock",
                                                    "text": "Central NOC/SOC — DKRLI",
                                                    "isSubtle": True,
                                                    "spacing": "None",
                                                },
                                            ],
                                        },
                                    ],
                                }
                            ],
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "📋 Título", "value": ocorrencia.titulo},
                                {"title": "📍 Dispositivo", "value": ocorrencia.local},
                                {
                                    "title": "👤 Registrado por",
                                    "value": ocorrencia.criado_por.username,
                                },
                                {
                                    "title": "🕐 Aberta em",
                                    "value": ocorrencia.criado_em.strftime(
                                        "%d/%m/%Y às %H:%M"
                                    ),
                                },
                            ],
                            "spacing": "Medium",
                        },
                        {
                            "type": "TextBlock",
                            "text": ocorrencia.descricao,
                            "wrap": True,
                            "color": "Default",
                            "spacing": "Small",
                        },
                        {
                            "type": "TextBlock",
                            "text": "Acesse o dashboard para acompanhar e encerrar quando resolvida.",
                            "wrap": True,
                            "isSubtle": True,
                            "spacing": "Medium",
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "🖥️ Acessar Dashboard",
                            "url": dashboard_url,
                            "style": "positive",
                        }
                    ],
                },
            }
        ],
    }
    return _post(payload)


def notificar_verificacao(ocorrencia, elapsed_seconds: int, dashboard_url: str) -> bool:
    """Envia verificação periódica (a cada minuto) perguntando se a ocorrência permanece."""
    elapsed = _elapsed_str(elapsed_seconds)
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Container",
                            "style": "warning",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "⏰  Ocorrência ainda aberta",
                                    "weight": "Bolder",
                                    "size": "Medium",
                                    "color": "Warning",
                                },
                                {
                                    "type": "TextBlock",
                                    "text": f"Tempo aberta: **{elapsed}**",
                                    "spacing": "None",
                                    "isSubtle": True,
                                },
                            ],
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "📋 Ocorrência", "value": ocorrencia.titulo},
                                {"title": "📍 Dispositivo", "value": ocorrencia.local},
                            ],
                            "spacing": "Small",
                        },
                        {
                            "type": "TextBlock",
                            "text": "**Esta ocorrência ainda permanece ou já foi resolvida?**\nAcesse o dashboard para confirmar ou encerrar.",
                            "wrap": True,
                            "color": "Attention",
                            "spacing": "Medium",
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "✅  Ainda está ocorrendo — ver dashboard",
                            "url": dashboard_url,
                            "style": "positive",
                        },
                        {
                            "type": "Action.OpenUrl",
                            "title": "🔴  Já foi resolvida — encerrar",
                            "url": dashboard_url,
                            "style": "destructive",
                        },
                    ],
                },
            }
        ],
    }
    return _post(payload)


def notificar_fechamento(ocorrencia, elapsed_seconds: int, dashboard_url: str) -> bool:
    """Envia notificação de ocorrência encerrada com o comentário de resolução do analista."""
    elapsed = _elapsed_str(elapsed_seconds)
    fechado_por = getattr(ocorrencia, "_fechado_por_username", "—")
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Container",
                            "style": "good",
                            "items": [
                                {
                                    "type": "ColumnSet",
                                    "columns": [
                                        {
                                            "type": "Column",
                                            "width": "auto",
                                            "items": [
                                                {
                                                    "type": "TextBlock",
                                                    "text": "✅",
                                                    "size": "ExtraLarge",
                                                }
                                            ],
                                        },
                                        {
                                            "type": "Column",
                                            "width": "stretch",
                                            "items": [
                                                {
                                                    "type": "TextBlock",
                                                    "text": "Ocorrência Encerrada",
                                                    "weight": "Bolder",
                                                    "size": "Large",
                                                    "color": "Good",
                                                },
                                                {
                                                    "type": "TextBlock",
                                                    "text": "Central NOC/SOC — DKRLI",
                                                    "isSubtle": True,
                                                    "spacing": "None",
                                                },
                                            ],
                                        },
                                    ],
                                }
                            ],
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "📋 Título", "value": ocorrencia.titulo},
                                {"title": "📍 Dispositivo", "value": ocorrencia.local},
                                {
                                    "title": "👤 Registrado por",
                                    "value": ocorrencia.criado_por.username,
                                },
                                {
                                    "title": "🔒 Encerrado por",
                                    "value": fechado_por,
                                },
                                {
                                    "title": "⏱️ Tempo até resolução",
                                    "value": elapsed,
                                },
                                {
                                    "title": "📅 Encerrado em",
                                    "value": ocorrencia.fechado_em.strftime(
                                        "%d/%m/%Y às %H:%M"
                                    ),
                                },
                            ],
                            "spacing": "Medium",
                        },
                        {
                            "type": "Container",
                            "style": "emphasis",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "💬 Comentário de resolução",
                                    "weight": "Bolder",
                                    "size": "Small",
                                    "spacing": "None",
                                },
                                {
                                    "type": "TextBlock",
                                    "text": ocorrencia.comentario_fechamento or "—",
                                    "wrap": True,
                                    "spacing": "Small",
                                },
                            ],
                            "spacing": "Medium",
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "🖥️ Ver Dashboard",
                            "url": dashboard_url,
                        }
                    ],
                },
            }
        ],
    }
    return _post(payload)
