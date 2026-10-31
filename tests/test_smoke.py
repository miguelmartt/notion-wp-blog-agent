"""Smoke tests — no credentials needed."""

import ast
import re
from pathlib import Path

from _env import ROOT, ba

parse_json_robusto = ba.parse_json_robusto


def test_parse_json_fences():
    assert parse_json_robusto('```json\n{"a": 1}\n```') == {"a": 1}


def test_word_count():
    assert ba.contar_palabras("<p>Hello world</p><h2>Title here</h2>") == 4


def test_no_h1_policy():
    cleaned, informe = ba.sanear_html("<h1>Bad</h1><p>Good intro</p>", "example.com")
    assert "<h1" not in cleaned.lower()
    assert "Good intro" in cleaned
    assert ba.resumen_saneado(informe) == ""  # dropping <h1> is policy, not an incident


def test_source_parses_as_python39():
    # Production runs Python 3.9: no 3.10+ syntax (match, except*, ...).
    source = (Path(ROOT) / "blog_automation.py").read_text(encoding="utf-8")
    ast.parse(source, feature_version=(3, 9))


def test_requirements_pinned():
    lines = [
        line.strip()
        for line in (Path(ROOT) / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert lines, "requirements.txt is empty"
    for line in lines:
        assert re.fullmatch(r"[A-Za-z0-9_.-]+==[0-9][\w.]*", line), line
