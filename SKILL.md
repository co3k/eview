---
name: eview
description: "Use for code review or property falsification passes."
version: 0.5.0
author: co3k
license: MIT
platforms: [linux, macos, windows]
---

# eview

A host-independent review protocol. Two sibling procedures share one pack:

- **review** — static: collect concerns, prove or carry them
- **property** — dynamic: falsify intended properties in a throwaway tree, in one of two
  lanes — a **sampled** lane (Hypothesis / fast-check) and an **exhaustive** lane (Lean
  `by decide`) for finite maps

No upstream prompt tree, no review binary, no forge, no orchestrator. Optional domain notes sit beside the protocol; they are not required.

## When to Use

- A commit, range, or PR needs a deep correctness review
- The user names the `eview` pack or the general review protocol
- A property / falsification pass is requested, or unverified premises from a review round should be tested
- The diff contains a finite map — a setting or permission table, an identification or
  resolution function, a state machine, a normalization, or a classification — and bounded
  absence matters: make the property procedure's exhaustive mode available. Without a `LANE`
  token, sampled remains the default.

Don't use for: posting review comments, implementing fixes, or treating the project's existing test suite as the review.

## Pack files

Load the referenced files with the agent host's skill or file loader (`file_path` labels
below). A CLI worker that cannot load skills must receive these files' absolute paths in its
handoff — never a host-specific fallback tree.

- `references/review-core.md` — static protocol (required for review)
- `references/false-positive-guide.md` — apply in Phase 2
- `references/property.md` — falsification protocol, both lanes (required for property)
- `references/lean.md` — exhaustive lane protocol (required for the Lean lane)
- `references/lean-handoff-example.md` — worked handoff and return shape for that lane
- `references/report-consumer-validation.md` — how a caller validates a report parser
- `references/domain-notes.md` — optional notes format
- `templates/handoff-review.md` / `templates/handoff-property.md`

## Procedure

### Review

1. Identify the mode and range (default: range mode, `HEAD`; full-tree mode when no range resolves). For a PR vs its base, use three-dot `BASE...HEAD`, not two-dot.
2. Load `references/review-core.md` and `references/false-positive-guide.md`.
   Resolve the handoff's `Previous report` line (one absolute path) and read it only if
   it exists; if it does not, there is no previous round (Phase 1b item 8 and 9a are
   `N/A`; 9b, 10, 11 and 12 still apply). Do not search for an earlier report.
3. If a notes directory is provided, load matching notes (`references/domain-notes.md`). If none, continue.
4. Follow review-core through collection, Phase 1b, verification, and report.
5. Done when the report has findings or an explicit none, a **Carried / unresolved** section, and **Unverified premises** (or "none"). Clean requires an empty carried list.

### Property

1. Do not run this inside the review hop. Use a separate write/execute tree.
2. Load `references/property.md`.
3. Feed it the review's unverified premises when they exist.
4. Pick the lane before writing anything:
   - **sampled** (default) — generate inputs, hunt a counterexample, classify it;
   - **exhaustive** (Lean) — the diff has a finite map and the question is absence.
     Load `references/lean.md`, follow `references/lean-handoff-example.md` for the handoff
     and return shape, and formalize the map outside the target repository with the target
     read-only.
5. Skip the exhaustive lane with `SKIPPED` and the reason when there is no finite executable
   map or no implementation, when the theorem would be trivially true, or when the question
   is a design judgement. Skipping is not a failure and does not downgrade the sampled lane.
6. Done when the return matches the lane's schema: sampled mode carries findings, a
   no-counterexample summary, carried items and the sampling-not-assurance line;
   exhaustive mode carries the property / result / theorem table, each counterexample with
   the production condition under which it fires, a fix predicate proved both to remove the
   counterexample and to keep the legitimate cases passing, the limits, and the artifact path.
   A skipped exhaustive-only return instead carries `status=SKIPPED`, the reason and evidence,
   plus notes; it requires no theorem table or `.lean` artifact.

## Caller integration (not a procedure)

A caller that parses a return validates its parser per
`references/report-consumer-validation.md` before trusting a parsed verdict: schema first,
then a row-by-row reconciliation against the raw report. A zero exit or an empty parsed list
never overrules nonempty raw findings. This is caller integration, not a third procedure.

## Relation to the upstream tool

A published reviewer binary (installable with `cargo install`) exists and is a different
artifact from this pack. Know the boundary so a request is not answered with the wrong one:

- That binary reviews a **closed set** of projects baked in at build time (`--project` is an
  enum, not a path). A new codebase needs a workflow added and rebuilt, not a directory.
- Its `--prompts DIR` replaces the prompt bundle and is the only runtime injection point;
  persona, stage instructions, and report validator stay compiled in.
- It ships `--agent` JSON output, `--stages` filtering, and `--custom-prompt`.
- This pack borrows the shape (root protocol plus optional domain notes) but depends on
  none of it, and runs equally under a plain agent session.

When the ask is "review this change the way we usually do", use the pack. When the ask is
"run that reviewer", use the binary and expect its project set, not yours.

## Pitfalls

- This pack is not a domain prompt tree and not a compiled review engine. Do not clone an upstream project as fallback.
- Do not fold property execution into the static review hop (read-only vs throwaway).
- "No counterexample" from the sampled lane is sampling, not a proof. The Lean lane exists for
  exactly that gap. The theorem closes only the stated property over the transcribed bounded
  domain; it does not verify the source system.
- A counterexample that cannot fire in production is not a finding. State the firing condition
  (input bound, window width, call order) or drop it.
- "Uniqueness holds" is not "identity holds". State the gate's coverage: what it prevents and
  what it does not (usability, ownership, freshness).
- Do not run the exhaustive lane on a diff with no implementation, or on a theorem that is a
  restatement of its own definitions. That is lane misuse; say `SKIPPED` and give the reason.
- Missing domain notes is not a failed review.
- Orchestrator paths, model binds, and report language belong in the handoff, not here.
- Any change to a procedure (`references/review-core.md`, `references/property.md`,
  `references/lean.md`) or to its handoff template requires a `version` bump here and
  in the `protocol:` lines of both handoff templates.
- The version string lives in exactly three places — this frontmatter, and one `protocol:`
  line in each of the two templates. Every other file must say "the `protocol:` line
  from the handoff", never restate the literal; a duplicated literal is what drifts at the
  next bump.
- A consumer that embeds this pack (a review lane, a CI job) carries its own `protocol:`
  line. Bumping here is incomplete until those consumers' handoff templates name the new
  version — the bump and the consumer edit are one change, not two.

## Verification

- Review return addresses Phase 1b items 1–12 (or marks N/A) and includes carried + premises sections.
- Sampled property return classifies every failure and names seeds.
- Exhaustive return has the property / result / theorem table, a production firing condition per
  counterexample, a fix predicate proved against the legitimate cases, and the stated limits.
- Skipped exhaustive-only return has `status=SKIPPED`, reason, evidence and notes, with no
  theorem table or Lean artifact.
