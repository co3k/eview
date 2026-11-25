# Handoff: property falsification

protocol: eview/0.5.0

Fill every placeholder. Paths are absolute; sandboxed workers may not expand variables.

## Goal

Hunt counterexamples in `BASE_SHA...HEAD_SHA`. Infer intended properties from evidence,
write property-based tests in `<THROWAWAY_ABS>`, execute, shrink, classify — or, when the
diff contains a finite map, formalize it in Lean and enumerate it with `by decide`. The
product is the report, not new tests in the repository.

## Pack

- Protocol: `<SKILL_DIR>/references/property.md`
- Exhaustive lane: `<SKILL_DIR>/references/lean.md` (required only for that lane)
- Exhaustive handoff shape: `<SKILL_DIR>/references/lean-handoff-example.md`

Read the protocol first; it defines lane selection, property selection, the tautology
guard, the classification (REAL-BUG / SPEC-AMBIGUITY / TEST-BUG), and the return schemas.

## Inputs

- `REPO_ABS`: `<REPO_ABS>` — read-only
- `THROWAWAY_ABS`: `<THROWAWAY_ABS>` — the only write/execute location
- `BASE_SHA` / `HEAD_SHA`: `<BASE_SHA>` / `<HEAD_SHA>`
- `SPEC_PATHS`: `<SPEC_ABS>`
- `FOCUS`: `<CHANGED_FILES_AND_CALLERS>`
- `TOOLCHAIN`: `<TEST_COMMAND>`
- `RUN_ABS` (optional artifact directory): `<RUN_ABS or none>` — required only when the
  caller wants files written; otherwise stdout is enough
- `PREMISES`: `<PREMISES or none>`
- `LANE`: `<sampled | exhaustive | auto>` — `auto` lets the worker apply the finite-map test

## Constraints

- Never mutate `<REPO_ABS>`. All execution happens in `<THROWAWAY_ABS>`.
- No pushes, comments, PR edits, or repository file edits.
- Budget: `<BUDGET>`. A selected lane whose own environment is blocked → stop that lane and
  carry it. No valuable properties → say so and stop. Budget reached → report partial results.
- Sampled lane only: Hypothesis `deadline=None`; bound examples (default ≤ 500 per property);
  record seeds. An exhaustive-only lane does not require a property library or repository runtime.
- Exhaustive lane: write the `.lean` project outside `<REPO_ABS>`; the target stays
  read-only. Do not add `.lean` files, `lake` projects, or generated tests to the repository.
- Exhaustive lane: transcribe the map from the code with `file:line` provenance, and do not
  change its meaning. If the diff has no finite map, or the theorem would be trivially true,
  or the question is a design judgement, return `SKIPPED` with the reason and evidence.

## Prior-round report

- Previous report — absolute path to one file (e.g. `/abs/dir/report.md`),
  never a directory or a relative path: `<PREVIOUS_REPORT_ABS or none>`

Read exactly this file when it exists; it supplies the review's premises, its carried
items, and the properties the prior round left open or judged as sampling only. If it does
not exist, there is no previous round: proceed without it, say so in `## Notes`, and do not
search for an earlier report. When it exists, `## Notes` records each of its unverified or
carried items and whether this pass reproduced, refuted, or left it open.

## Output

- Stream confirmed repros to stdout as they land.
- Sampled lane — finish with the sampled schema in the protocol: header (echoing the
  `protocol:` line above), findings, no-counterexample summary, carried, notes, and the
  sampling-not-assurance line.
- Exhaustive-only lane — finish with the protocol's exhaustive header and return: the
  property / result / theorem table, the counterexample with the production condition under
  which it fires, the fix predicate proved with the legitimate cases, the limits, and the
  `.lean` artifact's absolute path. Do not append the sampling disclaimer. The theorem closes
  only the stated property over the transcribed bounded domain; it does not verify the source
  system.
- Skipped exhaustive-only lane — finish with the protocol's `status=SKIPPED` header,
  `## Skipped` reason and evidence, and `## Notes`. No theorem table, `.lean` artifact, or
  build result is required because the lane did not execute.
- Both lanes — include both schemas. The sampling disclaimer is mandatory because sampling ran.

## Do not

- Add generated tests or `.lean` files to the repository.
- Claim a bug you cannot justify; a surprising failure is usually a wrong test.
- Report a counterexample as a finding without the production condition under which it fires.
- Present a sampled pass as proof, or an exhaustive pass as verification of anything beyond
  its transcribed bounded domain.
