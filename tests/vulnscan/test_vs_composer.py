"""composer.lock (spec: .specs/features/vuln-scan — LOCK-01..04)."""
from __future__ import annotations

import json

import pytest

from auditor.vulnscan.lockfiles import composer

PACKAGIST = "https://packagist.org/downloads/"

LOCK = {
    "packages": [
        {"name": "guzzlehttp/guzzle", "version": "7.4.0", "notification-url": PACKAGIST,
         "dist": {"type": "zip", "url": "https://api.github.com/repos/guzzle/guzzle/zipball/abc"}},
        {"name": "monolog/monolog", "version": "v2.3.5", "notification-url": PACKAGIST},
        {"name": "acme/billing", "version": "1.2.0",                       # repo privado no GitHub:
         "dist": {"type": "zip", "url": "https://api.github.com/repos/acme/billing/zipball/x"}},
        {"name": "acme/feature", "version": "dev-main", "notification-url": PACKAGIST},
    ],
    "packages-dev": [
        {"name": "phpunit/phpunit", "version": "9.5.10", "notification-url": PACKAGIST},
    ],
}


@pytest.fixture
def parsed(tmp_path):
    path = tmp_path / "composer.lock"
    path.write_text(json.dumps(LOCK, indent=4), encoding="utf-8")
    return path, {d.name: d for d in composer.parse_composer_lock(path, "composer.lock", tmp_path).dependencies}


def test_composer_public_package_and_version_line(parsed):
    path, deps = parsed
    g = deps["guzzlehttp/guzzle"]
    assert (g.ecosystem, g.version, g.dev, g.private) == ("Packagist", "7.4.0", False, False)
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if '"guzzlehttp/guzzle"' in ln)
    assert g.line == next(i for i in range(start, len(lines)) if '"version"' in lines[i]) + 1


def test_composer_v_prefix_is_normalized(parsed):
    assert parsed[1]["monolog/monolog"].version == "2.3.5"


def test_composer_without_packagist_notification_is_private(parsed):
    assert parsed[1]["acme/billing"].private is True        # URL do GitHub não basta (LOCK-03)


def test_composer_branch_versions_are_private(parsed):
    assert parsed[1]["acme/feature"].private is True        # dev-main não é release


def test_composer_packages_dev_are_dev(parsed):
    assert parsed[1]["phpunit/phpunit"].dev is True and parsed[1]["guzzlehttp/guzzle"].dev is False


@pytest.mark.parametrize("text", ["não é json", "[]", '{"packages": "x"}'])
def test_composer_malformed_never_raises(tmp_path, text):
    path = tmp_path / "composer.lock"
    path.write_text(text, encoding="utf-8")
    result = composer.parse_composer_lock(path, "composer.lock", tmp_path)
    assert result.dependencies == [] and len(result.errors) == 1
