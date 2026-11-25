# Worked handoff — Lean exhaustive lane

This is a companion shape, not a standalone handoff. Start from
`templates/handoff-property.md`, keep its `protocol:` line, and use the sections below when
`LANE=exhaustive`.

Run: `<run_id>`
Range: `<BASE>...<HEAD>` (three-dot)
Repo: `<REPO_ABS>` (read-only)
Protocol: `<SKILL_DIR>/references/lean.md` (required reading)
Previous report: `<PREVIOUS_REPORT_ABS>` or `none`

Keep the parent property's `protocol:` line; do not restate a version literal here.

## What this hop does

Formalize a **finite map** from the diff in Lean 4 and enumerate it with `by decide`. The
question is not "did sampling find a counterexample" but "does a counterexample exist in the
bounded domain".

## Choosing the target

Read the diff and pick the function or table that is one of:

- a setting / permission table (value → mode, permission, behaviour)
- an identification or resolution function (input → exactly one target)
- a state machine (state × event → state)
- a normalization / equivalence (string → string)
- a classification (input → one of a finite set of classes)

**If none is present, decide `SKIPPED` and record the reason, then stop.** Skipping is not a
failure; manufacturing trivial theorems is.

## Deliverables

When the lane executes:

1. `<THROWAWAY_ABS>/<name>.lean` — the formalization and the theorems (`lake build` passes)
2. The report below — write it to `<RUN_ABS>/return-lean.md` only when `RUN_ABS` was supplied;
   otherwise return it on stdout.

```text
| property | result | theorem |
|---|---|---|
| <text> | holds / counterexample / skipped | `theorem_name` |
```

Plus:

- **Counterexample**: the minimal input and the production condition under which it fires
- **Fix**: written as a predicate, proved as a pair — the counterexample is gone **and** the
  legitimate cases still pass
- **Limits**: what was not checked (infinite domain, external API, order dependence), and how
  the bounded domain was bounded
- **Artifact**: the absolute `.lean` path and the tail of the `lake build` output
- **Scope statement**: The theorem closes only the stated property over the transcribed
  bounded domain; it does not verify the source system. For an exhaustive-only run, do not
  append the sampled lane's sampling disclaimer.

When the lane is skipped before formalization, return only:

```text
pack=eview/property | protocol=<value of the parent handoff's protocol: line> | repo=<name> | range <base12>...<head12> | model=<id> | wall <Nm> | lane=exhaustive | status=SKIPPED

## Skipped
reason: <no finite executable map | no implementation | trivially true | design judgement>
evidence: <file/range inspected>

## Notes
<previous-report reconciliation and limits>
```

No `.lean` artifact or `lake build` result is required on this path. Write the report to
`RUN_ABS` only when supplied; otherwise return it on stdout.

## Constraints

- Read-only on the target repository: no edits, commits, pushes, or comments.
- Do not change the code's meaning; leave `file:line` provenance for every transcription.
- Do not invent numbers. What was not checked is written as "not checked".
