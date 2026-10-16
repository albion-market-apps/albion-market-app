"""Varredura periódica de alertas ativos contra os preços mais recentes.

TODO (fase 2): rodar como job do worker (ou APScheduler na API), lendo `alerts`
ativos, comparando com o último `price` da (item_id, city_id) e disparando
notificação (ex.: publicar em um canal Redis dedicado a notificações).
"""
