"""Regressão de escopo das tools (spec: .specs/features/search-code-scoping/spec.md).

G25/G26: ``search_code`` não pode ler nada fora da raiz (glob com '..', glob absoluto,
symlink para fora). G30: regras de ignore/testes valem para o caminho RELATIVO à raiz.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from auditor.config import Settings
from auditor.tools.filesystem import make_project_tools
from auditor.tools.project import detect_stack

SECRET = "SECRET_OUTSIDE_ROOT_42"


def _search(root: Path, **kwargs) -> str:
    tools = {t.name: t for t in make_project_tools(root, Settings())}
    return tools["search_code"].invoke(kwargs)


@pytest.fixture
def layout(tmp_path: Path) -> Path:
    """tmp/outside/s.txt (segredo) + tmp/proj/src/{a.py, out_link.txt -> ../../outside/s.txt}."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "s.txt").write_text(f"{SECRET}\n", encoding="utf-8")
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "a.py").write_text("needle = 1\n", encoding="utf-8")
    (root / "src" / "out_link.txt").symlink_to(outside / "s.txt")
    return root


# --- SCOPE-01: glob com componente '..' é rejeitado --------------------------------
@pytest.mark.parametrize("glob", ["../outside/*", "src/../../outside/*", "..\\outside\\*"])
def test_glob_with_parent_component_is_rejected(layout, glob):
    out = _search(layout, pattern=SECRET, glob=glob)
    assert out.startswith("ERRO:")
    assert SECRET not in out


def test_dotdot_inside_a_name_is_not_a_traversal(layout):
    (layout / "src" / "weird..py").write_text("needle = 2\n", encoding="utf-8")
    out = _search(layout, pattern="needle", glob="**/*..py")
    assert out == "src/weird..py:1: needle = 2"


# --- SCOPE-02: glob absoluto é rejeitado sem exceção --------------------------------
def test_absolute_glob_is_rejected(layout):
    out = _search(layout, pattern=SECRET, glob=str(layout.parent / "outside" / "*"))
    assert out.startswith("ERRO:")
    assert SECRET not in out


# --- SCOPE-03: symlink para fora da raiz não vaza conteúdo -------------------------
def test_symlink_to_outside_is_not_searched(layout):
    out = _search(layout, pattern=SECRET)
    assert SECRET not in out
    assert out == "(nenhum resultado)"


# --- SCOPE-04: symlink interno continua pesquisável, pelo caminho do link -----------
def test_symlink_inside_root_is_searched_under_its_own_path(layout):
    (layout / "src" / "in_link.py").symlink_to(layout / "src" / "a.py")
    out = _search(layout, pattern="needle")
    assert set(out.splitlines()) == {"src/a.py:1: needle = 1", "src/in_link.py:1: needle = 1"}


# --- SCOPE-05: ancestral com nome ignorado não esconde o projeto --------------------
@pytest.mark.parametrize("ancestor", ["build", "env", "bin"])
def test_ignored_ancestor_name_does_not_hide_project(tmp_path, ancestor):
    root = tmp_path / ancestor / "proj"
    root.mkdir(parents=True)
    (root / "main.py").write_text("needle = 1\n", encoding="utf-8")
    assert _search(root, pattern="needle") == "main.py:1: needle = 1"


# --- SCOPE-06: diretório ignorado DENTRO do projeto continua ignorado ----------------
def test_ignored_dir_inside_project_still_skipped(tmp_path):
    root = tmp_path / "proj"
    (root / "node_modules").mkdir(parents=True)
    (root / "node_modules" / "x.js").write_text("needle = 1\n", encoding="utf-8")
    (root / "app.js").write_text("needle = 2\n", encoding="utf-8")
    assert _search(root, pattern="needle") == "app.js:1: needle = 2"


# --- SCOPE-07 / SCOPE-08: has_tests depende só do caminho relativo -----------------
def test_has_tests_ignores_ancestor_named_tests(tmp_path):
    root = tmp_path / "tests" / "proj"
    root.mkdir(parents=True)
    (root / "main.py").write_text("x = 1\n", encoding="utf-8")
    assert detect_stack(root, Settings()).has_tests is False


def test_has_tests_true_when_project_has_tests_dir(tmp_path):
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_x.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    assert detect_stack(root, Settings()).has_tests is True
