# Handoff: review

protocol: eview/0.5.0

Fill every placeholder. Paths are absolute; do not use shell variables — sandboxed workers
may not expand them.

## Goal

Deep static correctness review of `RANGE`. Do not open prior published reports for content
except the one named under *Prior-round report* below.

## Repo / HEAD

- Path: `<REPO_ABS>`
- HEAD: `<HEAD_SHA>`
- Base: `<BASE_SHA>`
- Mode: `range <BASE>...<HEAD>` | `full-tree` (for a PR use three-dot `BASE...HEAD`, not two-dot; full-tree takes no range)
- Diff: `<DIFF_ABS or none>`

## Review pack

- Protocol: `<SKILL_DIR>/references/review-core.md`
- False positives: `<SKILL_DIR>/references/false-positive-guide.md`
- Domain notes: `<NOTES_DIR or none>`

Read the protocol file first and follow it. It defines collection, Phase 1b items 1–12,
disposition, carried list, and the report shape.

## Tests (verified) — do not re-run

- command: `<TEST_COMMAND>`
- result: `<COUNTS>` (`<DATE>`)

Use these counts. Do not re-run the suite unless this section says to.

## Spec pointers

- `<SPEC_ABS>` — sections that bind the change
- Out of range: `<SIBLING_PRS or none>` (context only)
- Known external facts: `<FACTS or none>` (re-prove any load-bearing one)

## Hot paths

- `<PATH>` — `<FUNCTION_OR_MODULE>`

## Focus

- `<PR_SPECIFIC_THEME>`

## Prior-round report

This section declares the handoff's one prior-report line; no other section repeats it.

- Previous report — absolute path to one file (e.g. `/abs/dir/report.md`),
  never a directory or a relative path: `<PREVIOUS_REPORT_ABS or none>`

Read exactly this file when it exists (Phase 1b item 8 and 9a and the carried list depend
on it). If it does not exist, there is no previous round: record item 8 and 9a as `N/A`
with that reason and do not search the repository, the run directory, or the forge for an
earlier report. Item 9b, item 10, item 11 and item 12 do not read this file and still apply.
Do not read any other prior report for content.

## Output

- Start with the `protocol:` line copied verbatim from the top of this handoff.
- Stream findings to stdout as each high is proven; the caller captures them.
- One line per finding: `id | severity | file:function | concern | evidence | status`.
  Severity is `critical|high|medium|low`; status is `reported|carried`; evidence is the
  traced path. Cite function and file, not line numbers.
- Answer Phase 1b items 1–12, each with `N/A` and the reason when it cannot apply.
- Item 8 applies to every fix from the previous round: 8a lists every site with the same
  pattern and confirms the fix at each; 8b lists what the fix must now handle and what the
  pre-fix code handled, then traces both through the fixed code.
- Item 9 names, for each previous-round fix, the input where pre-fix and fixed behaviour
  differ, where that input is exercised, and the verdict (discriminated / undiscriminated /
  premise). A test that passes before and after the fix is not evidence, and an expectation
  built by calling the code under test is not a witness.
- Item 10 traces the call order of every changed call chain: what runs first, what returns
  early, and which side effect that short-circuit skips.
- Item 11 traces every reset, dedupe set, or idempotency key the change touches: the unit
  that owns it (request, item, round, process, store), whether the second use in that unit
  is suppressed or passes, and the one input whose second use must differ from the first.
- Item 12 traces every check that decides pass or refusal: which field it reads as its
  material, which field or command it judges, and whether both land on the same subject
  (a lint that reads its own task text to decide is judge and judged in one artifact).
- One return shape only — the protocol's: protocol line, one findings list, one answer per
  item 1–12, then `## Carried / unresolved` and `## Unverified premises`. No second schema.
- No product patches, no git writes, no forge posts.
- End with `## Carried / unresolved` and `## Unverified premises` (say "none" when empty).

## Do not

- Read any prior published review output other than the previous report named above.
- Re-run the verified test suite.
- Load a different project's prompt tree.
