# tests/test_total_e2e.py
from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_total_e2e_case(case_name: str, e2e_ctx, pytestconfig: pytest.Config) -> None:
    """
    1 케이스 = 1 pytest 테스트
    """
    from tests import e2e_total_lib as e2e

    case = e2e_ctx.cases_by_name[case_name]

    if pytestconfig.getoption("--show-payload") and case.payload is not None:
        print("\n[PAYLOAD]", case_name)
        print(e2e.jprint(case.payload))

    w0 = e2e_ctx.warning_count()
    resp = None
    case_failed = False

    try:
        resp = case.run(e2e_ctx)

        if not e2e_ctx.quiet:
            print("\n[SUMMARY]", case_name)
            print(e2e.summarize_any(resp, all_stages=e2e_ctx.summary_all))

        case.validate(resp, e2e_ctx)

        warned = e2e_ctx.warning_count() > w0
        if warned and case_name in e2e_ctx.case_warnings:
            print("\n[WARN]", case_name)
            for w in e2e_ctx.case_warnings.get(case_name, []):
                print("-", w)

        if e2e_ctx.strict and (e2e_ctx.warning_count() > w0):
            raise AssertionError("Warnings treated as failures (--strict)")

    except Exception:
        case_failed = True
        raise

    finally:
        warned = e2e_ctx.warning_count() > w0

        if e2e_ctx.should_dump(failed=case_failed, warned=warned):
            if case.payload is not None:
                e2e_ctx.dump_json(case_name, "payload.json", case.payload)
            if resp is not None:
                e2e_ctx.dump_json(case_name, "response.json", resp)

                if isinstance(resp, dict) and resp.get("_kind") == "report_flow":
                    e2e_ctx.dump_json(
                        case_name,
                        "debug_sim_payload.json",
                        resp.get("_debug_sim_payload"),
                    )
                    e2e_ctx.dump_json(
                        case_name,
                        "debug_sim_response.json",
                        resp.get("_debug_sim_response"),
                    )
                    e2e_ctx.dump_json(
                        case_name,
                        "debug_enqueue_response.json",
                        resp.get("_debug_enqueue_response"),
                    )
