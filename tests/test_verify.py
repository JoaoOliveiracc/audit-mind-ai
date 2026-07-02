"""Testes do nó de verificação de evidência (determinístico, sem LLM)."""
from __future__ import annotations

from pathlib import Path

from auditor.nodes.verify import _evidence_matches, verify_node


def _make_project(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "db.py").write_text(
        "PASSWORD = 'SuperSecret123'\n\ndef get_user(conn, id):\n"
        "    return conn.query('SELECT * FROM users WHERE id = ' + id)\n",
        encoding="utf-8",
    )
    return tmp_path


def test_evidence_matches_tolerates_whitespace_and_linenumbers():
    content = "def get_user(conn, id):\n    return conn.query('SELECT ... ' + id)\n"
    # evidência copiada com prefixo de número de linha e indentação diferente
    assert _evidence_matches("  3|     return conn.query('SELECT ... ' + id)", content)
    assert not _evidence_matches("os.system('rm -rf /')", content)


def test_verify_node_filters_hallucinations(tmp_path):
    root = _make_project(tmp_path)
    findings = [
        # 1) real: evidência existe no arquivo -> verified
        {"title": "Hardcoded secret", "severity": "critical", "file": "src/db.py",
         "line": 1, "evidence": "PASSWORD = 'SuperSecret123'", "confidence": 0.9},
        # 2) arquivo inexistente -> rejected
        {"title": "Bug em arquivo fantasma", "severity": "high", "file": "src/ghost.py",
         "evidence": "whatever", "confidence": 0.8},
        # 3) evidência fabricada (não está no arquivo) -> rejected
        {"title": "Vuln inventada", "severity": "high", "file": "src/db.py",
         "evidence": "eval(user_input)  # não existe", "confidence": 0.95},
        # 4) achado arquitetural sem arquivo -> unverified (mantido, confiança rebaixada)
        {"title": "Sem camadas", "severity": "medium", "file": None,
         "evidence": None, "confidence": 0.9},
    ]
    state = {"project_path": str(root), "findings": findings}
    out = verify_node(state)

    kept = out["findings"]
    stats = out["verification"]
    titles = {f["title"] for f in kept}

    assert stats["verified"] == 1
    assert stats["rejected"] == 2
    assert stats["unverified"] == 1
    assert titles == {"Hardcoded secret", "Sem camadas"}
    assert "Bug em arquivo fantasma" in stats["rejected_titles"]
    assert "Vuln inventada" in stats["rejected_titles"]

    verified = next(f for f in kept if f["title"] == "Hardcoded secret")
    assert verified["verified"] is True

    arch = next(f for f in kept if f["title"] == "Sem camadas")
    assert arch["verified"] is False
    assert arch["confidence"] <= 0.5  # rebaixada por não ter evidência conferível
