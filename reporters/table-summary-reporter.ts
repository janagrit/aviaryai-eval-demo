import type { FullResult, Reporter, TestCase, TestResult } from "@playwright/test/reporter"

/**
 * End-of-run table summary for Playwright: the running environment, one
 * table per section (describe block), a combined table, and Passed /
 * Failed / Skipped totals. Same layout as reporters/table_summary.py for
 * pytest. No dependencies.
 */

type Outcome = "passed" | "failed" | "skipped"

interface Row {
  readonly section: string
  readonly name: string
  readonly outcome: Outcome
  readonly durationMs: number
}

export interface TableSummaryOptions {
  /** Where lines go; defaults to stdout. Tests inject a collector. */
  write?: (line: string) => void
  /** ANSI colors; defaults to on for a TTY unless NO_COLOR is set. */
  color?: boolean
}

const LABELS: Record<Outcome, string> = { passed: "Passed", failed: "Failed", skipped: "Skipped" }
const COLORS: Record<Outcome | "blue", number> = { passed: 32, failed: 31, skipped: 33, blue: 34 }
const MAX_NAME_WIDTH = 70

function toOutcome(status: TestResult["status"]): Outcome {
  if (status === "passed" || status === "skipped") return status
  return "failed" // failed, timedOut, interrupted
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)}s`
  const seconds = Math.floor(ms / 1000)
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

function truncate(text: string, width: number): string {
  return text.length <= width ? text : `${text.slice(0, width - 1)}…`
}

export function renderTable(head: readonly string[], rows: readonly (readonly string[])[]): string[] {
  const widths = head.map((cell, i) => Math.max(cell.length, ...rows.map((row) => row[i].length)))
  const border = `+${widths.map((w) => "-".repeat(w + 2)).join("+")}+`
  const line = (cells: readonly string[]) =>
    `| ${cells.map((cell, i) => cell.padEnd(widths[i])).join(" | ")} |`
  return [border, line(head), border, ...rows.map(line), border]
}

export default class TableSummaryReporter implements Reporter {
  private rows: ReadonlyMap<string, Row> = new Map()
  private readonly write: (line: string) => void
  private readonly color: boolean

  constructor(options: TableSummaryOptions = {}) {
    this.write = options.write ?? ((line) => process.stdout.write(`${line}\n`))
    this.color = options.color ?? (Boolean(process.stdout.isTTY) && !process.env.NO_COLOR)
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    // Keyed by test id, so a retry replaces the earlier attempt.
    const row: Row = {
      section: test.parent?.title || "Unknown Suite",
      name: test.title,
      outcome: toOutcome(result.status),
      durationMs: result.duration,
    }
    this.rows = new Map([...this.rows, [test.id, row]])
  }

  onEnd(_result: FullResult): void {
    const environment = (process.env.ENVIRONMENT || "local").toUpperCase()
    this.write("")
    this.write(this.paint("=== Final Summary for All Sections ===", null, true))
    this.write(this.paint(`Running Environment: ${environment}`, null, true))

    const rows = [...this.rows.values()]
    if (rows.length === 0) {
      this.write(this.paint("No test results recorded.", COLORS.skipped))
      return
    }

    const sections = new Map<string, Row[]>()
    for (const row of rows) sections.set(row.section, [...(sections.get(row.section) ?? []), row])
    for (const [section, sectionRows] of sections) {
      this.write("")
      this.write(this.paint(`${section} Section Summary:`, COLORS.blue, true))
      this.writeTable(["Test Name", "Status", "Duration"], sectionRows, false)
    }

    this.write("")
    this.writeTable(["Test Suite", "Test Name", "Status", "Duration"], rows, true)

    this.write("")
    this.write(`Total Tests: ${rows.length}`)
    for (const outcome of Object.keys(LABELS) as Outcome[]) {
      const count = rows.filter((row) => row.outcome === outcome).length
      this.write(this.paint(`${LABELS[outcome]}: ${count}`, COLORS[outcome]))
    }
  }

  private writeTable(head: string[], rows: readonly Row[], withSection: boolean): void {
    const cells = rows.map((row) => [
      ...(withSection ? [row.section] : []),
      truncate(row.name, MAX_NAME_WIDTH),
      LABELS[row.outcome],
      formatDuration(row.durationMs),
    ])
    for (const line of renderTable(head, cells)) this.write(line)
  }

  private paint(text: string, colorCode: number | null, bold = false): string {
    if (!this.color) return text
    const codes = [...(bold ? [1] : []), ...(colorCode === null ? [] : [colorCode])]
    return codes.length ? `\x1b[${codes.join(";")}m${text}\x1b[0m` : text
  }
}
