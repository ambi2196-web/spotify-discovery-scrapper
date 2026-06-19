"""Phase 0 smoke tests: scaffold imports, config parses, collectors register."""

from datetime import datetime, timezone

import scrapper.collectors  # noqa: F401  (registers collectors on import)
from scrapper import DIAGNOSTIC_QUESTIONS
from scrapper.config import load_config
from scrapper.models import Review, Source
from scrapper.registry import available


def test_six_diagnostic_questions():
    assert len(DIAGNOSTIC_QUESTIONS) == 6


def test_config_parses_and_lists_enabled_sources():
    cfg = load_config()
    assert cfg.window_days > 0
    assert "reddit" in cfg.enabled_sources()


def test_collectors_register():
    assert {"app_store", "play_store", "reddit"}.issubset(set(available()))


def test_review_autogenerates_id():
    r = Review(
        source=Source.REDDIT,
        source_url="https://x",
        created_at=datetime.now(timezone.utc),
        text="hi",
    )
    assert r.id and len(r.id) == 16
