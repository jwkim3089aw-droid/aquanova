# tests/conftest.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, List

import pytest

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # type: ignore


DEFAULT_E2E_BASE_URL = os.getenv("AQUANOVA_E2E_BASE_URL", "http://127.0.0.1:8003")
DEFAULT_E2E_TIMEOUT = float(os.getenv("AQUANOVA_E2E_TIMEOUT", "30"))


@dataclass(frozen=True)
class E2EConfig:
    enabled: bool
    base_url: str
    timeout_s: float
    quiet: bool
    strict: bool
    only: Optional[str]
    no_reports: bool

    def log(self, msg: str) -> None:
        if not self.quiet:
            print(msg, flush=True)


def pytest_addoption(parser: pytest.Parser) -> None:
    g = parser.getgroup("aquanova-e2e")

    g.addoption(
        "--e2e",
        action="store_true",
        default=False,
        help="Run E2E tests (marked with @pytest.mark.e2e).",
    )
    g.addoption(
        "--e2e-base-url",
        action="store",
        default=DEFAULT_E2E_BASE_URL,
        help=f"Base URL for the running API server (default: {DEFAULT_E2E_BASE_URL}).",
    )
    g.addoption(
        "--e2e-timeout",
        action="store",
        type=float,
        default=DEFAULT_E2E_TIMEOUT,
        help=f"HTTP timeout seconds for E2E calls (default: {DEFAULT_E2E_TIMEOUT}).",
    )
    g.addoption(
        "--e2e-only",
        action="store",
        default=None,
        help="Run only E2E tests whose nodeid contains this substring (e.g. hrro_).",
    )
    g.addoption(
        "--e2e-quiet",
        action="store_true",
        default=False,
        help="Reduce E2E extra prints.",
    )
    g.addoption(
        "--e2e-strict",
        action="store_true",
        default=False,
        help="Strict E2E mode: fail (instead of skip) if server connectivity check fails.",
    )
    g.addoption(
        "--e2e-no-reports",
        action="store_true",
        default=False,
        help="Skip tests marked @pytest.mark.reports (report generation) in E2E runs.",
    )


def pytest_configure(config: pytest.Config) -> None:
    # Register markers so pytest doesn't warn
    config.addinivalue_line(
        "markers", "e2e: end-to-end tests (require running API server)"
    )
    config.addinivalue_line(
        "markers", "reports: tests that generate PDF/report artifacts"
    )


def _get_e2e_config(config: pytest.Config) -> E2EConfig:
    return E2EConfig(
        enabled=bool(config.getoption("--e2e")),
        base_url=str(config.getoption("--e2e-base-url")).rstrip("/"),
        timeout_s=float(config.getoption("--e2e-timeout")),
        quiet=bool(config.getoption("--e2e-quiet")),
        strict=bool(config.getoption("--e2e-strict")),
        only=config.getoption("--e2e-only"),
        no_reports=bool(config.getoption("--e2e-no-reports")),
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: List[pytest.Item]
) -> None:
    """
    - Default: skip all @pytest.mark.e2e (and @pytest.mark.reports) unless --e2e is passed.
    - If --e2e-only is set: keep only tests whose nodeid contains that substring.
    - If --e2e-no-reports: skip tests marked @pytest.mark.reports
    """
    e2e = _get_e2e_config(config)

    # 1) Skip E2E / reports unless enabled
    if not e2e.enabled:
        skip_e2e = pytest.mark.skip(reason="E2E tests are disabled. Re-run with --e2e")
        for item in items:
            if "e2e" in item.keywords or "reports" in item.keywords:
                item.add_marker(skip_e2e)
        return

    # 2) If --e2e-no-reports, skip reports-marked tests
    if e2e.no_reports:
        skip_reports = pytest.mark.skip(
            reason="Report tests are disabled via --e2e-no-reports"
        )
        for item in items:
            if "reports" in item.keywords:
                item.add_marker(skip_reports)

    # 3) If --e2e-only is set, deselect non-matching tests (nodeid contains substring)
    if e2e.only:
        needle = str(e2e.only)
        selected: List[pytest.Item] = []
        deselected: List[pytest.Item] = []

        for item in items:
            if needle in item.nodeid:
                selected.append(item)
            else:
                deselected.append(item)

        if deselected:
            config.hook.pytest_deselected(items=deselected)
            items[:] = selected


@pytest.fixture(scope="session")
def e2e_cfg(pytestconfig: pytest.Config) -> E2EConfig:
    """
    Session-wide E2E configuration, derived from CLI options.
    """
    return _get_e2e_config(pytestconfig)


@pytest.fixture(scope="session")
def e2e_client(e2e_cfg: E2EConfig):
    """
    HTTP client for calling a running AquaNova API server.
    Requires: pip install httpx
    """
    if httpx is None:
        msg = "httpx is not installed. Install it: pip install httpx"
        if e2e_cfg.strict:
            raise RuntimeError(msg)
        pytest.skip(msg)

    timeout = httpx.Timeout(e2e_cfg.timeout_s)
    client = httpx.Client(
        base_url=e2e_cfg.base_url, timeout=timeout, follow_redirects=True
    )

    # Light connectivity check (doesn't assume a specific health endpoint exists).
    # In strict mode: fail if cannot connect at all.
    try:
        # Try a few common paths; accept any response as "server reachable".
        for path in ("/docs", "/openapi.json", "/"):
            try:
                r = client.get(path)
                e2e_cfg.log(
                    f"[E2E] server check: GET {e2e_cfg.base_url}{path} -> {r.status_code}"
                )
                break
            except Exception:
                continue
        else:
            # nothing worked
            raise RuntimeError("Could not reach server on common endpoints")
    except Exception as exc:
        client.close()
        if e2e_cfg.strict:
            raise
        pytest.skip(f"E2E server not reachable: {exc}")

    yield client
    client.close()


@pytest.fixture()
def require_e2e(e2e_cfg: E2EConfig) -> None:
    """
    Optional helper fixture:
    - If a test isn't marked @pytest.mark.e2e but still needs E2E guard, call/require this fixture.
    """
    if not e2e_cfg.enabled:
        pytest.skip("E2E disabled. Re-run with --e2e")
