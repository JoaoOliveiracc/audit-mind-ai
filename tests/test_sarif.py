"""Testes do exportador SARIF (offline, sem LLM)."""
import json

from auditor.report.sarif import build_sarif, render_sarif


def _state() -> dict:
    return {
        "findings": [
            {
                "dimension": "security", "title": "SQL injection",
                "severity": "critical", "description": "entrada concatenada na query",
                "recommendation": "usar parâmetros", "file": "app/db.py", "line": 12,
                "evidence": "query = 'SELECT ...' + user", "confidence": 0.9, "verified": True,
            },
            {
                "dimension": "quality", "title": "TODO esquecido",
                "severity": "info", "description": "comentário TODO", "recommendation": "remover",
                "file": None, "confidence": 0.5,
            },
        ]
    }


def test_sarif_top_level_structure():
    doc = build_sarif(_state())
    assert doc["version"] == "2.1.0"
    driver = doc["runs"][0]["tool"]["driver"]
    assert driver["name"] == "Audit Mind AI"
    assert driver["version"]  # versão do pacote preenchida
    assert len(doc["runs"][0]["results"]) == 2


def test_sarif_severity_to_level():
    results = build_sarif(_state())["runs"][0]["results"]
    assert results[0]["level"] == "error"  # critical -> error
    assert results[1]["level"] == "note"   # info -> note


def test_sarif_location_and_rule_id():
    results = build_sarif(_state())["runs"][0]["results"]
    r0 = results[0]
    assert r0["ruleId"] == "audit-mind/security"
    phys = r0["locations"][0]["physicalLocation"]
    assert phys["artifactLocation"]["uri"] == "app/db.py"
    assert phys["region"]["startLine"] == 12
    # achado sem arquivo não deve emitir locations
    assert "locations" not in results[1]


def test_sarif_rules_one_per_dimension():
    rules = build_sarif(_state())["runs"][0]["tool"]["driver"]["rules"]
    assert {r["id"] for r in rules} == {"audit-mind/security", "audit-mind/quality"}


def test_sarif_is_valid_json():
    parsed = json.loads(render_sarif(_state()))
    assert parsed["$schema"].endswith("sarif-2.1.0.json")


def test_sarif_empty_findings():
    doc = build_sarif({"findings": []})
    assert doc["runs"][0]["results"] == []
    assert doc["runs"][0]["tool"]["driver"]["rules"] == []
