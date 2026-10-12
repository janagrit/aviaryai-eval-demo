import { expect, test } from "@playwright/test"
import type { FullResult, TestCase, TestResult } from "@playwright/test/reporter"

import TableSummaryReporter from "../reporters/table-summary-reporter"

// Unit tests for the end-of-run table: fake test results in, printed lines out.

function fakeTest(id: string, title: string, suite: string): TestCase {
  return { id, title, parent: { title: suite } } as unknown as TestCase
}

function fakeResult(status: TestResult["status"], duration = 12): TestResult {
  return { status, duration } as unknown as TestResult
}

function run(feed: (reporter: TableSummaryReporter) => void): string[] {
  const lines: string[] = []
  const reporter = new TableSummaryReporter({ write: (line) => lines.push(line), color: false })
  feed(reporter)
  reporter.onEnd({ status: "passed" } as FullResult)
  return lines
}

function indexOfLine(lines: string[], pattern: RegExp): number {
  return lines.findIndex((line) => pattern.test(line))
}

test.describe("Table summary reporter", () => {
  test("prints a table per section, a combined table, and totals", () => {
    const lines = run((r) => {
      r.onTestEnd(fakeTest("1", "loads the page", "Chat page"), fakeResult("passed"))
      r.onTestEnd(fakeTest("2", "leaks nothing", "Adversarial"), fakeResult("failed"))
      r.onTestEnd(fakeTest("3", "later", "Adversarial"), fakeResult("skipped"))
      r.onTestEnd(fakeTest("4", "hangs", "Adversarial"), fakeResult("timedOut"))
    })

    const order = [
      /Final Summary for All Sections/,
      /Chat page Section Summary:/,
      /\| loads the page +\| Passed +\| 12ms/,
      /Adversarial Section Summary:/,
      /\| leaks nothing +\| Failed/,
      /\| later +\| Skipped/,
      /\| hangs +\| Failed/,
      /\| Test Suite +\| Test Name +\| Status +\| Duration/,
      /^Total Tests: 4$/,
      /^Passed: 1$/,
      /^Failed: 2$/,
      /^Skipped: 1$/,
    ].map((pattern) => indexOfLine(lines, pattern))

    expect(order).not.toContain(-1)
    expect(order).toEqual([...order].sort((a, b) => a - b))
  })

  test("counts a retried test once, using its final attempt", () => {
    const lines = run((r) => {
      r.onTestEnd(fakeTest("1", "flaky", "Chat page"), fakeResult("failed"))
      r.onTestEnd(fakeTest("1", "flaky", "Chat page"), fakeResult("passed"))
    })

    expect(lines).toContain("Total Tests: 1")
    expect(lines).toContain("Passed: 1")
    expect(lines).toContain("Failed: 0")
  })

  test("prints the environment from $ENVIRONMENT, defaulting to LOCAL", () => {
    const saved = process.env.ENVIRONMENT
    try {
      process.env.ENVIRONMENT = "ci"
      expect(run(() => {})).toContain("Running Environment: CI")

      delete process.env.ENVIRONMENT
      expect(run(() => {})).toContain("Running Environment: LOCAL")
    } finally {
      if (saved === undefined) delete process.env.ENVIRONMENT
      else process.env.ENVIRONMENT = saved
    }
  })

  test("reports when no tests ran", () => {
    expect(run(() => {})).toContain("No test results recorded.")
  })
})
