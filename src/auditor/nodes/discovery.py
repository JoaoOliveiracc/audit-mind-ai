"""Nó de descoberta: varre o projeto e detecta a stack."""
from __future__ import annotations

from pathlib import Path

from ..config import get_settings
from ..state import AuditState
from ..tools.project import build_inventory, detect_stack


def discovery_node(state: AuditState) -> dict:
    """Detecta linguagens/frameworks e monta o inventário do projeto."""
    settings = get_settings()
    root = Path(state["project_path"]).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Caminho do projeto inválido: {root}")

    profile = detect_stack(root, settings)
    inventory = build_inventory(root, settings)

    return {
        "stack_profile": profile.model_dump(),
        "inventory": inventory,
        "status": "discovered",
    }
