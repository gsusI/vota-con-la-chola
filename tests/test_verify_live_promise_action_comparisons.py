from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest import SkipTest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/verify_live_promise_action_comparisons.py"
PUBLISHED_ARTIFACT = (
    REPO_ROOT / "etl/data/published/promise-action-comparisons-v1.json"
)
PUBLIC_ARTIFACT = (
    REPO_ROOT / "ui/gh-pages-next/public/comparisons/data/comparisons.json"
)
BUILT_PAGE = REPO_ROOT / "ui/gh-pages-next/out/comparisons/index.html"
BUILT_ARTIFACT = (
    REPO_ROOT / "ui/gh-pages-next/out/comparisons/data/comparisons.json"
)
EXPECTED_RELEASE = "vclc:comparison-release:ea65f3b8104dd678cb7ebce724b78f86"
EXPECTED_SEMANTIC_SHA256 = (
    "7b37c75c836a0a85c0aab70b7165a5ce005cef320c22c49e34ec650969691b19"
)


def load_verifier():
    specification = importlib.util.spec_from_file_location(
        "verify_live_promise_action_comparisons", SCRIPT
    )
    module = importlib.util.module_from_spec(specification)
    assert specification.loader is not None
    specification.loader.exec_module(module)
    return module


def test_real_generated_comparison_artifact_satisfies_live_contract() -> None:
    verifier = load_verifier()
    published_bytes = PUBLISHED_ARTIFACT.read_bytes()
    public_bytes = PUBLIC_ARTIFACT.read_bytes()
    artifact = json.loads(public_bytes)

    assert published_bytes == public_bytes
    assert verifier.HEX_SHA256.fullmatch(verifier.sha256_bytes(public_bytes))
    assert artifact["release_id"] == EXPECTED_RELEASE
    assert artifact["semantic_sha256"] == EXPECTED_SEMANTIC_SHA256

    checks, errors, probe_targets = verifier.validate_artifact_contract(
        artifact,
        expected_release=EXPECTED_RELEASE,
        expected_semantic_sha256=EXPECTED_SEMANTIC_SHA256,
        label="real generated",
    )

    assert errors == []
    assert checks
    assert all(checks.values()), checks
    assert [host for host, _url in probe_targets] == list(
        verifier.PROBE_HOST_PRIORITY
    )
    assert all(
        verifier.official_source_host(url) == host
        for host, url in probe_targets
    )
    primary_source_urls = {
        edge["source_url"]
        for item in artifact["items"]
        for edge in item["evidence"]
        if edge["evidence_role"] == "primary"
        and edge["evidence_side"] in {"claim", "action"}
    }
    assert all(url in primary_source_urls for _host, url in probe_targets)


def test_actual_static_build_preserves_exact_artifact_and_route_markers() -> None:
    if not BUILT_PAGE.is_file() or not BUILT_ARTIFACT.is_file():
        raise SkipTest(
            "static build absent; run the repository frontend build before this check"
        )

    verifier = load_verifier()
    public_bytes = PUBLIC_ARTIFACT.read_bytes()
    built_bytes = BUILT_ARTIFACT.read_bytes()
    page_text = BUILT_PAGE.read_text(encoding="utf-8")

    assert built_bytes == public_bytes
    assert verifier.sha256_bytes(built_bytes) == verifier.sha256_bytes(public_bytes)
    assert all(marker in page_text for marker in verifier.PAGE_MARKERS)
    assert "MARÍA CARMEN DA SILVA MÉNDEZ" in page_text
    assert "Néstor Rego Candamil" in page_text
