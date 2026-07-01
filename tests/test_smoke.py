"""Testes de fumaça que não dependem do LLM (rápidos e offline)."""
from __future__ import annotations

from pathlib import Path

from auditor.config import Settings
from auditor.report.renderer import build_context, render_html, render_markdown
from auditor.state import Severity
from auditor.tools.filesystem import make_project_tools
from auditor.tools.project import build_inventory, detect_stack


def _make_sample_project(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text(
        "PASSWORD = 'hardcoded-secret'\n\ndef run():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "package.json").write_text('{"name":"x"}', encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    return tmp_path


def test_detect_stack(tmp_path):
    root = _make_sample_project(tmp_path)
    profile = detect_stack(root, Settings())
    assert "Python" in profile.languages
    assert profile.has_tests is True
    assert "npm/yarn/pnpm" in profile.package_managers
    assert profile.total_files >= 3


def test_inventory_not_empty(tmp_path):
    root = _make_sample_project(tmp_path)
    inv = build_inventory(root, Settings())
    assert "main.py" in inv


def test_filesystem_tools_and_traversal_guard(tmp_path):
    root = _make_sample_project(tmp_path)
    tools = {t.name: t for t in make_project_tools(root, Settings())}

    listing = tools["list_directory"].invoke({"path": "."})
    assert "app/" in listing

    content = tools["read_file"].invoke({"path": "app/main.py"})
    assert "hardcoded-secret" in content

    search = tools["search_code"].invoke({"pattern": "PASSWORD", "glob": "**/*.py"})
    assert "main.py" in search

    # path traversal deve ser bloqueado
    blocked = tools["read_file"].invoke({"path": "../../etc/passwd"})
    assert "ERRO" in blocked


def test_report_rendering():
    state = {
        "project_path": "/tmp/proj",
        "user_goal": "Auditoria de segurança",
        "user_context": {"Ambiente?": "produção"},
        "health_score": 62,
        "executive_summary": "Resumo de teste.",
        "stack_profile": {"languages": {"Python": 3}, "frameworks": ["Node.js"],
                          "total_files": 3, "total_loc": 10, "has_tests": True,
                          "has_ci": False, "has_docker": False, "has_git": True,
                          "package_managers": ["pip"]},
        "plan": {"dimensions": ["security"], "focus_notes": ""},
        "dimension_summaries": [{"dimension": "security", "summary": "ok"}],
        "findings": [
            {"dimension": "security", "title": "Segredo hardcoded",
             "severity": Severity.CRITICAL.value, "description": "Senha no código.",
             "recommendation": "Use variáveis de ambiente.", "file": "app/main.py",
             "line": 1, "evidence": "PASSWORD = '...'", "confidence": 0.95},
        ],
    }
    ctx = build_context(state, generated_at="2026-07-01 12:00:00")
    md = render_markdown(ctx)
    html = render_html(ctx)
    assert "Segredo hardcoded" in md
    assert "Crítico" in md
    assert "<html" in html
    assert "62" in html
