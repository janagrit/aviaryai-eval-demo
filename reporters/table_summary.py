"""End-of-run table summary for pytest.

Python port of table-summary-reporter.js (a Playwright reporter): one
table per section (test file, or file::Class), then a combined table and
Passed / Failed / Skipped totals. Wired in by tests/conftest.py; uses
only the standard library.
"""

import os
from dataclasses import dataclass

STATUS_LABELS = {"passed": "Passed", "failed": "Failed", "skipped": "Skipped"}
STATUS_COLORS = {"passed": "green", "failed": "red", "skipped": "yellow"}
MAX_NAME_WIDTH = 70


@dataclass(frozen=True)
class TestRow:
    section: str
    name: str
    outcome: str
    duration: float


def running_environment():
    """Value of $ENVIRONMENT (e.g. "ci"), upper-cased; LOCAL when unset."""
    return (os.environ.get("ENVIRONMENT") or "local").upper()


def format_duration(seconds):
    if seconds < 1:
        return "%dms" % round(seconds * 1000)
    if seconds < 60:
        return "%.2fs" % seconds
    minutes, rest = divmod(int(seconds), 60)
    return "%dm %ds" % (minutes, rest)


def _truncate(text, width):
    return text if len(text) <= width else text[: width - 1] + "…"


def render_table(head, rows):
    """Render rows as a boxed plain-text table; returns a list of lines."""
    widths = [
        max(len(str(cell)) for cell in column) for column in zip(head, *rows)
    ]
    border = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def line(cells):
        return "| " + " | ".join(
            str(c).ljust(w) for c, w in zip(cells, widths)
        ) + " |"

    return [border, line(head), border, *(line(r) for r in rows), border]


class TableSummaryPlugin:
    def __init__(self):
        self._rows = {}

    def pytest_runtest_logreport(self, report):
        # Reruns (pytest-rerunfailures) report "rerun"; the final attempt wins.
        if report.outcome == "rerun":
            return
        # The call phase decides the result; setup/teardown only matter
        # when they fail or skip the test.
        if report.when != "call" and report.outcome == "passed":
            return
        if report.when == "teardown" and report.nodeid in self._rows:
            if report.outcome != "failed":
                return
        section, _, name = report.nodeid.rpartition("::")
        row = TestRow(section or "Unknown Suite", name, report.outcome, report.duration)
        self._rows = {**self._rows, report.nodeid: row}

    def pytest_terminal_summary(self, terminalreporter):
        tr = terminalreporter
        tr.section("Final Summary for All Sections")
        tr.write_line("Running Environment: %s" % running_environment(), bold=True)
        rows = list(self._rows.values())
        if not rows:
            tr.write_line("No test results recorded.", yellow=True)
            return

        sections = {}
        for row in rows:
            sections = {**sections, row.section: sections.get(row.section, ()) + (row,)}
        for section, section_rows in sections.items():
            tr.write_line("")
            tr.write_line("%s Section Summary:" % section, blue=True, bold=True)
            self._write_table(tr, ["Test Name", "Status", "Duration"], section_rows, False)

        tr.write_line("")
        self._write_table(
            tr, ["Test Suite", "Test Name", "Status", "Duration"], rows, True
        )

        counts = {k: sum(1 for r in rows if r.outcome == k) for k in STATUS_LABELS}
        tr.write_line("")
        tr.write_line("Total Tests: %d" % len(rows))
        for outcome, label in STATUS_LABELS.items():
            tr.write_line(
                "%s: %d" % (label, counts[outcome]),
                **{STATUS_COLORS[outcome]: True},
            )

    @staticmethod
    def _write_table(tr, head, rows, with_section):
        cells = [
            ([r.section] if with_section else [])
            + [
                _truncate(r.name, MAX_NAME_WIDTH),
                STATUS_LABELS.get(r.outcome, r.outcome),
                format_duration(r.duration),
            ]
            for r in rows
        ]
        for text in render_table(head, cells):
            tr.write_line(text)


def pytest_configure(config):
    # One instance per session, so nested runs (pytester) don't share state.
    config.pluginmanager.register(TableSummaryPlugin(), "table-summary")
