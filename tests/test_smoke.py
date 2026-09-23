"""Smoke tests — no credentials needed."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blog_automation import parse_json_robusto


def test_parse_json_fences():
    assert parse_json_robusto('```json\n{"a": 1}\n```') == {"a": 1}


def test_word_count():
    html_text = "<p>Hello world</p><h2>Title here</h2>"
    words = len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", html_text)))
    assert words == 4


def test_no_h1_policy():
    html_text = "<h1>Bad</h1><p>Good intro</p>"
    cleaned = re.sub(r"(?is)<h1.*?>.*?</h1>", "", html_text).strip()
    assert "<h1" not in cleaned.lower()
    assert "Good intro" in cleaned
