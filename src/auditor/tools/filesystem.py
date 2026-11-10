"""Ferramentas de sistema de arquivos escopadas à raiz do projeto (read-only, seguras)."""
from __future__ import annotations

import os
import re
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Iterator

from langchain_core.tools import StructuredTool

from ..config import Settings


def _safe_resolve(root: Path, rel_path: str) -> Path:
    """Resolve ``rel_path`` sob ``root`` impedindo path traversal para fora do projeto."""
    candidate = (root / rel_path).resolve()
    root_resolved = root.resolve()
    if root_resolved != candidate and root_resolved not in candidate.parents:
        raise ValueError(f"Acesso negado: '{rel_path}' está fora da raiz do projeto.")
    return candidate


def _glob_segments(glob: str) -> list[str]:
    """Segmentos do glob (``/``), sem ``.`` e vazios — ``'./src//*.py'`` → ``['src', '*.py']``."""
    return [seg for seg in glob.replace("\\", "/").split("/") if seg not in ("", ".")]


def _glob_matches(parts: tuple[str, ...], segs: list[str]) -> bool:
    """Casa um caminho relativo (partes) com o glob: ``fnmatchcase`` por segmento e ``**`` =
    zero ou mais diretórios (no fim, qualquer arquivo abaixo)."""
    if not segs:
        return not parts
    if segs[0] == "**":
        return any(_glob_matches(parts[i:], segs[1:]) for i in range(len(parts) + 1))
    return bool(parts) and fnmatchcase(parts[0], segs[0]) and _glob_matches(parts[1:], segs[1:])


def _iter_glob_files(root: Path, segs: list[str], ignore_dirs) -> Iterator[Path]:
    """Arquivos sob ``root`` que casam com ``segs``, ordenados pelo caminho relativo (G34).

    Poda ``ignore_dirs`` antes de listar, não segue diretórios-link e, sem ``**``, não
    desce além da profundidade do padrão.
    """
    max_dirs = None if "**" in segs else len(segs) - 1   # profundidade máxima de diretórios
    matches: list[tuple[str, ...]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = Path(dirpath).relative_to(root).parts
        if max_dirs is not None and len(rel_dir) >= max_dirs:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
        matches.extend((*rel_dir, n) for n in filenames if _glob_matches((*rel_dir, n), segs))
    # Só nomes foram listados até aqui (barato); ordena por caminho relativo e entrega.
    for parts in sorted(matches, key="/".join):
        yield root.joinpath(*parts)


def make_project_tools(root: Path, settings: Settings) -> list[StructuredTool]:
    """Cria ferramentas read-only vinculadas a um projeto específico.

    As ferramentas são intencionalmente somente-leitura: o agent audita, não altera.
    """

    def read_file(path: str, start_line: int = 1, max_lines: int = 400) -> str:
        """Lê um arquivo de texto do projeto.

        Args:
            path: Caminho relativo à raiz do projeto.
            start_line: Linha inicial (1-indexada).
            max_lines: Número máximo de linhas a retornar.
        """
        try:
            target = _safe_resolve(root, path)
        except ValueError as exc:
            return f"ERRO: {exc}"
        if not target.is_file():
            return f"ERRO: arquivo não encontrado: {path}"
        if target.suffix.lower() in settings.binary_extensions:
            return f"ERRO: '{path}' parece ser binário; leitura ignorada."
        try:
            if target.stat().st_size > settings.max_file_bytes:
                note = f"[aviso: arquivo grande, exibindo até {max_lines} linhas a partir de {start_line}]\n"
            else:
                note = ""
            with target.open("r", encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()
        except OSError as exc:
            return f"ERRO ao ler '{path}': {exc}"
        start = max(0, start_line - 1)
        chunk = lines[start:start + max_lines]
        numbered = "".join(f"{start + i + 1:>5}| {ln}" for i, ln in enumerate(chunk))
        return f"{note}{numbered}" if numbered else "(arquivo vazio)"

    def list_directory(path: str = ".") -> str:
        """Lista arquivos e subdiretórios de um diretório do projeto.

        Args:
            path: Caminho relativo à raiz (padrão: raiz).
        """
        try:
            target = _safe_resolve(root, path)
        except ValueError as exc:
            return f"ERRO: {exc}"
        if not target.is_dir():
            return f"ERRO: diretório não encontrado: {path}"
        items = []
        for child in sorted(target.iterdir()):
            if child.name in settings.ignore_dirs:
                continue
            suffix = "/" if child.is_dir() else ""
            items.append(f"{child.name}{suffix}")
        return "\n".join(items) if items else "(diretório vazio)"

    def search_code(pattern: str, glob: str = "**/*", is_regex: bool = False) -> str:
        """Busca por um padrão de texto no código do projeto (grep recursivo).

        Args:
            pattern: Texto ou expressão regular a procurar.
            glob: Padrão glob de arquivos (ex.: '**/*.py'). Padrão: todos.
            is_regex: Se True, trata ``pattern`` como regex.
        """
        # O glob vem do LLM (e, por prompt injection, do código auditado): nada de
        # padrões absolutos ou com componente '..' — a busca fica confinada à raiz.
        if Path(glob).is_absolute() or ".." in re.split(r"[\\/]", glob):
            return "ERRO: glob deve ser relativo à raiz do projeto e sem '..'."
        segs = _glob_segments(glob)
        if not segs:
            return "ERRO: glob vazio — use, por exemplo, '**/*' ou '**/*.py'."
        try:
            matcher = re.compile(pattern if is_regex else re.escape(pattern), re.IGNORECASE)
        except re.error as exc:
            return f"ERRO: regex inválida: {exc}"
        results: list[str] = []
        for path in _iter_glob_files(root, segs, settings.ignore_dirs):
            if not path.is_file():
                continue
            try:  # symlink cujo alvo real está fora da raiz: não lê
                _safe_resolve(root, path.relative_to(root).as_posix())
            except ValueError:
                continue
            # ignore_dirs já foi aplicado aos DIRETÓRIOS no walk (G30/G34); arquivos com
            # esses nomes (ex.: um script `build`) são pesquisados (SRCH-08).
            if path.suffix.lower() in settings.binary_extensions:
                continue
            try:
                if path.stat().st_size > settings.max_file_bytes:
                    continue
                with path.open("r", encoding="utf-8", errors="ignore") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if matcher.search(line):
                            rel = path.relative_to(root).as_posix()
                            results.append(f"{rel}:{lineno}: {line.strip()[:200]}")
                            if len(results) >= settings.max_search_results:
                                results.append(f"... (limite de {settings.max_search_results} resultados atingido)")
                                return "\n".join(results)
            except OSError:
                continue
        return "\n".join(results) if results else "(nenhum resultado)"

    return [
        StructuredTool.from_function(read_file),
        StructuredTool.from_function(list_directory),
        StructuredTool.from_function(search_code),
    ]
