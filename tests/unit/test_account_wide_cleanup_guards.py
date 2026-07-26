from pathlib import Path


def test_non_dry_run_cancel_all_tests_require_dedicated_account_gate() -> None:
    tests_root = Path(__file__).parents[1]
    unguarded: list[str] = []
    for path in tests_root.rglob("*.py"):
        source = path.read_text()
        if "cancel_all(" not in source:
            continue
        calls_account_wide_cancel = any(
            "cancel_all(" in line and "dry_run=True" not in line for line in source.splitlines()
        )
        if calls_account_wide_cancel and "account_wide_cleanup_enabled" not in source:
            unguarded.append(str(path.relative_to(tests_root)))
    assert unguarded == []
