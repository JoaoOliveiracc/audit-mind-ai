"""Detecção de stack e construção do inventário do projeto (agnóstico de linguagem)."""
from __future__ import annotations

import os
from pathlib import Path

from ..config import Settings
from ..state import StackProfile

# Mapa extensão -> linguagem (amostra ampla, agnóstica de stack).
EXT_LANGUAGE: dict[str, str] = {
    ".py": "Python", ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".jsx": "JavaScript",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".scala": "Scala",
    ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".cpp": "C++", ".cc": "C++", ".c": "C",
    ".h": "C/C++ Header", ".hpp": "C++ Header", ".swift": "Swift", ".m": "Objective-C",
    ".dart": "Dart", ".ex": "Elixir", ".exs": "Elixir", ".clj": "Clojure",
    ".sql": "SQL", ".sh": "Shell", ".bash": "Shell", ".ps1": "PowerShell",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".vue": "Vue", ".svelte": "Svelte",
    ".yaml": "YAML", ".yml": "YAML", ".json": "JSON", ".toml": "TOML", ".tf": "Terraform",
    ".md": "Markdown",
}

# Arquivos-marcadores -> (gerenciador de pacotes, framework/ecosistema).
MARKER_SIGNALS: dict[str, tuple[str, str]] = {
    "package.json": ("npm/yarn/pnpm", "Node.js"),
    "requirements.txt": ("pip", "Python"),
    "pyproject.toml": ("pip/poetry/uv", "Python"),
    "Pipfile": ("pipenv", "Python"),
    "go.mod": ("go modules", "Go"),
    "Cargo.toml": ("cargo", "Rust"),
    "pom.xml": ("maven", "Java/JVM"),
    "build.gradle": ("gradle", "Java/JVM"),
    "build.gradle.kts": ("gradle", "Kotlin/JVM"),
    "Gemfile": ("bundler", "Ruby"),
    "composer.json": ("composer", "PHP"),
    "pubspec.yaml": ("pub", "Dart/Flutter"),
    "mix.exs": ("mix", "Elixir"),
    "Package.swift": ("spm", "Swift"),
}

FRAMEWORK_HINTS: dict[str, str] = {
    "next.config.js": "Next.js", "next.config.mjs": "Next.js", "nuxt.config.ts": "Nuxt",
    "angular.json": "Angular", "vite.config.ts": "Vite", "vite.config.js": "Vite",
    "manage.py": "Django", "artisan": "Laravel", "nest-cli.json": "NestJS",
    "gatsby-config.js": "Gatsby", "svelte.config.js": "SvelteKit",
    "application.properties": "Spring", "application.yml": "Spring",
}

CI_MARKERS = (".github/workflows", ".gitlab-ci.yml", "azure-pipelines.yml",
              "Jenkinsfile", ".circleci", "bitbucket-pipelines.yml")
TEST_HINTS = ("test", "tests", "spec", "__tests__")


def _iter_files(root: Path, settings: Settings):
    """Percorre o projeto respeitando diretórios ignorados e limite de arquivos."""
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in settings.ignore_dirs]
        for name in filenames:
            count += 1
            if count > settings.max_files:
                return
            yield Path(dirpath) / name


def detect_stack(root: Path, settings: Settings) -> StackProfile:
    """Detecta linguagens, frameworks e características do projeto."""
    languages: dict[str, int] = {}
    package_managers: set[str] = set()
    frameworks: set[str] = set()
    markers: list[str] = []
    total_files = 0
    total_loc = 0
    has_tests = False

    for path in _iter_files(root, settings):
        total_files += 1
        rel = path.relative_to(root).as_posix()
        name = path.name
        ext = path.suffix.lower()

        if any(part.lower() in TEST_HINTS for part in path.parts):
            has_tests = True

        if name in MARKER_SIGNALS:
            pm, eco = MARKER_SIGNALS[name]
            package_managers.add(pm)
            frameworks.add(eco)
            markers.append(rel)
        if name in FRAMEWORK_HINTS:
            frameworks.add(FRAMEWORK_HINTS[name])

        if ext in EXT_LANGUAGE and ext not in settings.binary_extensions:
            lang = EXT_LANGUAGE[ext]
            languages[lang] = languages.get(lang, 0) + 1
            try:
                if path.stat().st_size <= settings.max_file_bytes:
                    with path.open("r", encoding="utf-8", errors="ignore") as fh:
                        total_loc += sum(1 for _ in fh)
            except OSError:
                pass

    has_ci = any((root / m).exists() for m in CI_MARKERS)
    has_docker = (root / "Dockerfile").exists() or (root / "docker-compose.yml").exists()
    has_git = (root / ".git").exists()

    return StackProfile(
        languages=dict(sorted(languages.items(), key=lambda kv: kv[1], reverse=True)),
        frameworks=sorted(frameworks),
        package_managers=sorted(package_managers),
        marker_files=markers,
        has_tests=has_tests,
        has_ci=has_ci,
        has_docker=has_docker,
        has_git=has_git,
        total_files=total_files,
        total_loc=total_loc,
    )


def build_inventory(root: Path, settings: Settings, max_entries: int = 400) -> str:
    """Gera uma árvore textual resumida do projeto para dar contexto ao agent."""
    lines: list[str] = []
    entries = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in settings.ignore_dirs)
        rel_dir = Path(dirpath).relative_to(root)
        depth = 0 if rel_dir == Path(".") else len(rel_dir.parts)
        if depth > 4:
            dirnames[:] = []
            continue
        indent = "  " * depth
        if rel_dir != Path("."):
            lines.append(f"{indent}{rel_dir.name}/")
        for name in sorted(filenames):
            entries += 1
            if entries > max_entries:
                lines.append(f"{indent}  ... (inventário truncado em {max_entries} entradas)")
                return "\n".join(lines)
            lines.append(f"{indent}  {name}")
    return "\n".join(lines)
