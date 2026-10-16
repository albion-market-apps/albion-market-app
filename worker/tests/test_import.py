"""Smoke test: garante que o worker importa sem erro (sem bater em rede/DB real)."""

from worker_app import collector, config


def test_modules_import() -> None:
    assert config.get_settings().poll_interval_seconds > 0
    assert callable(collector.fetch_prices)
