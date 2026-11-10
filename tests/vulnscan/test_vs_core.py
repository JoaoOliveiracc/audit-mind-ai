"""Núcleo puro do vulnscan (spec: .specs/features/vuln-scan — OSV-02 severidade; versões)."""
from __future__ import annotations

import pytest

from auditor.vulnscan.severity import cvss3_base_score, severity_from_osv, severity_from_score
from auditor.vulnscan.versions import in_range, normalize_name, version_key


# --- CVSS v3.x base score: vetores com nota oficial conhecida (NVD/FIRST) -------------
@pytest.mark.parametrize("vector, score", [
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8),
    ("CVSS:3.1/AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H", 7.2),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", 10.0),
    ("CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N", 5.5),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N", 6.1),
    ("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N", 0.0),
])
def test_cvss3_base_score_matches_official_values(vector, score):
    assert cvss3_base_score(vector) == score


@pytest.mark.parametrize("vector", ["CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N",
                                    "lixo", "CVSS:3.1/AV:N", "CVSS:3.1/AV:X/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"])
def test_cvss3_unsupported_or_malformed_returns_none(vector):
    assert cvss3_base_score(vector) is None


@pytest.mark.parametrize("score, sev", [(0.0, "info"), (0.1, "low"), (3.9, "low"), (4.0, "medium"),
                                        (6.9, "medium"), (7.0, "high"), (8.9, "high"), (9.0, "critical")])
def test_score_bands(score, sev):
    assert severity_from_score(score) == sev


# --- precedência: rótulo da base (GHSA) → CVSS v3 → medium + nota -------------------
@pytest.mark.parametrize("label, sev", [("LOW", "low"), ("MODERATE", "medium"), ("MEDIUM", "medium"),
                                        ("HIGH", "high"), ("CRITICAL", "critical")])
def test_severity_prefers_database_label(label, sev):
    record = {"database_specific": {"severity": label},
              "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}]}
    assert severity_from_osv(record) == (sev, None)


def test_severity_falls_back_to_highest_cvss3():
    record = {"severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"},
                           {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}]}
    assert severity_from_osv(record) == ("critical", None)


def test_severity_unknown_is_medium_with_note():
    sev, note = severity_from_osv({"severity": [{"type": "CVSS_V4", "score": "CVSS:4.0/..."}]})
    assert sev == "medium" and note == "severidade não informada pela fonte"


# --- versões por ecossistema ----------------------------------------------------------
@pytest.mark.parametrize("eco, older, newer", [
    ("npm", "4.17.15", "4.17.21"), ("npm", "1.0.0-beta.2", "1.0.0"), ("npm", "v2.9.9", "2.10.0"),
    ("npm", "1.0.0-alpha", "1.0.0-beta"),
    ("Packagist", "7.4.0", "7.4.5"), ("Packagist", "v1.2.3", "1.10.0"),
    ("PyPI", "2.4.1", "2.10"), ("PyPI", "1.0rc1", "1.0"), ("PyPI", "1.0", "1.0.post1"),
])
def test_version_order(eco, older, newer):
    assert version_key(eco, older) < version_key(eco, newer)


@pytest.mark.parametrize("v, intro, fixed, expected", [
    ("4.17.15", "0", "4.17.21", True), ("4.17.21", "0", "4.17.21", False),
    ("3.9.0", "4.0.0", "4.17.21", False), ("5.0.0", "4.0.0", None, True),
])
def test_in_range(v, intro, fixed, expected):
    assert in_range("npm", v, intro, fixed) is expected


# --- OSV-01: nomes PyPI normalizados pela PEP 503; npm/Packagist como escritos --------
@pytest.mark.parametrize("eco, raw, norm", [
    ("PyPI", "Django", "django"), ("PyPI", "zope_interface", "zope-interface"),
    ("PyPI", "Foo.._-Bar", "foo-bar"), ("npm", "@Scope/Pkg", "@Scope/Pkg"),
    ("Packagist", "Guzzlehttp/Guzzle", "Guzzlehttp/Guzzle"),
])
def test_normalize_name(eco, raw, norm):
    assert normalize_name(eco, raw) == norm
