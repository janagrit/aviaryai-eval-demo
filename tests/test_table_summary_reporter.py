"""Tests for the end-of-run table summary (reporters/table_summary.py).

Each test runs a throwaway pytest session in a temp dir via pytester and
checks the printed summary. Run with: python -m pytest tests/
"""

pytest_plugins = ["pytester"]

CONFTEST = "from reporters.table_summary import pytest_configure  # noqa: F401\n"


def _run(pytester, source):
    pytester.makeconftest(CONFTEST)
    pytester.makepyfile(test_sample=source)
    return pytester.runpytest()


def test_prints_a_section_table_and_totals_for_mixed_outcomes(pytester):
    result = _run(
        pytester,
        """
        import pytest

        def test_ok():
            pass

        def test_bad():
            assert False

        @pytest.mark.skip(reason="not today")
        def test_later():
            pass
        """,
    )

    result.stdout.fnmatch_lines(
        [
            "*Final Summary for All Sections*",
            "*test_sample.py Section Summary:*",
            "*test_ok*Passed*",
            "*test_bad*Failed*",
            "*test_later*Skipped*",
            "Total Tests: 3",
            "Passed: 1",
            "Failed: 1",
            "Skipped: 1",
        ]
    )


def test_a_setup_error_counts_as_failed(pytester):
    result = _run(
        pytester,
        """
        import pytest

        @pytest.fixture
        def broken():
            raise RuntimeError("boom")

        def test_uses_broken(broken):
            pass
        """,
    )

    result.stdout.fnmatch_lines(["*test_uses_broken*Failed*", "Failed: 1"])


def test_parametrized_cases_are_listed_separately(pytester):
    result = _run(
        pytester,
        """
        import pytest

        @pytest.mark.parametrize("n", [1, 2])
        def test_n(n):
            pass
        """,
    )

    result.stdout.fnmatch_lines(
        ["*test_n[[]1[]]*Passed*", "*test_n[[]2[]]*Passed*", "Total Tests: 2"]
    )


def test_prints_the_environment_from_the_environment_variable(pytester, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "ci")

    result = _run(pytester, "def test_ok():\n    pass\n")

    result.stdout.fnmatch_lines(["Running Environment: CI"])


def test_environment_defaults_to_local_when_unset(pytester, monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    result = _run(pytester, "def test_ok():\n    pass\n")

    result.stdout.fnmatch_lines(["Running Environment: LOCAL"])


def test_table_is_the_last_thing_printed(pytester):
    result = _run(
        pytester,
        """
        def test_ok():
            pass

        def test_bad():
            assert False
        """,
    )

    # After pytest's own short summary and its final "1 failed, 1 passed" line.
    result.stdout.fnmatch_lines(
        [
            "*short test summary info*",
            "*1 failed, 1 passed*",
            "*Final Summary for All Sections*",
            "Skipped: 0",
        ]
    )
    assert result.stdout.lines[-1] == "Skipped: 0"


def test_reports_when_no_tests_ran(pytester):
    result = _run(pytester, "x = 1\n")

    result.stdout.fnmatch_lines(["*No test results recorded.*"])
