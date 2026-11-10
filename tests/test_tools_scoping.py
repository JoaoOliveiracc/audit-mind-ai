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


# --- G34: busca podada + glob por segmento (search-and-judge-perf: SRCH-01..07) ---------
import os  # noqa: E402

_FILES = ["top.py", "README.md", "src/a.py", "src/b.ts", "src/deep/c.py", "src/deep/test_x.py",
          "tests/test_y.py", "node_modules/pkg/index.js", "node_modules/pkg/z.py", ".venv/lib/v.py"]


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    for rel in _FILES:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("NEEDLE\n", encoding="utf-8")
    (root / "linkdir").symlink_to(root / "src" / "deep", target_is_directory=True)
    return root


def _found(root: Path, glob: str) -> list[str]:
    out = _search(root, pattern="NEEDLE", glob=glob)
    return [] if out == "(nenhum resultado)" else [line.split(":", 1)[0] for line in out.splitlines()]


@pytest.mark.parametrize("glob, expected", [
    ("**/*", ["README.md", "src/a.py", "src/b.ts", "src/deep/c.py", "src/deep/test_x.py",
              "tests/test_y.py", "top.py"]),
    ("*.py", ["top.py"]),
    ("src/*.py", ["src/a.py"]),
    ("**/*.py", ["src/a.py", "src/deep/c.py", "src/deep/test_x.py", "tests/test_y.py", "top.py"]),
    ("src/**/*.py", ["src/a.py", "src/deep/c.py", "src/deep/test_x.py"]),
    ("**/test_*.py", ["src/deep/test_x.py", "tests/test_y.py"]),
    ("src/**", ["src/a.py", "src/b.ts", "src/deep/c.py", "src/deep/test_x.py"]),
])
def test_srch02_glob_semantics_and_srch07_order(tree, glob, expected):
    assert _found(tree, glob) == expected            # lista exata e ordenada (SRCH-07)


@pytest.fixture
def scanned(monkeypatch):
    seen: list[str] = []
    real = os.scandir

    def spy(path="."):
        seen.append(os.path.normpath(os.fspath(path)))   # caminho literal (não resolve links)
        return real(path)

    monkeypatch.setattr(os, "scandir", spy)
    return seen


def test_srch01_ignored_dirs_are_never_listed(tree, scanned):
    _found(tree, "**/*")
    root = str(tree)
    for ignored in ("node_modules", ".venv"):
        assert not any(p == os.path.join(root, ignored) or p.startswith(os.path.join(root, ignored) + os.sep)
                       for p in scanned), ignored


def test_srch03_depth_bounded_glob_does_not_descend(tree, scanned):
    assert _found(tree, "src/*.py") == ["src/a.py"]
    assert os.path.join(str(tree), "src", "deep") not in scanned


def test_srch04_symlinked_dirs_are_not_descended(tree, scanned):
    found = _found(tree, "**/*")
    assert not any(f.startswith("linkdir/") for f in found)
    link = os.path.join(str(tree), "linkdir")
    assert not any(p == link or p.startswith(link + os.sep) for p in scanned)   # nunca listado
    assert found.count("src/deep/c.py") == 1          # alvo pesquisado uma vez, pelo caminho real


@pytest.mark.parametrize("glob", ["", "."])
def test_srch06_empty_or_dot_glob_is_a_tool_error(tree, glob):
    assert _search(tree, pattern="NEEDLE", glob=glob).startswith("ERRO:")



# --- SRCH-08: só DIRETÓRIOS são ignorados; arquivos com esses nomes são pesquisados ---------
@pytest.mark.parametrize("name", ["build", "env", "bin", "out"])
def test_srch08_files_named_like_ignored_dirs_are_searched(tmp_path, name):
    root = tmp_path / "proj"
    root.mkdir()
    (root / name).write_text("NEEDLE\n", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts" / name).write_text("NEEDLE\n", encoding="utf-8")
    assert _found(root, "**/*") == [name, f"scripts/{name}"]          # ordem de caminho (SRCH-07)
