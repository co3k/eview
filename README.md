# eview

A host-independent review pack with two sibling procedures: a static **review** and a
dynamic **property** (falsification) pass. The property pass defaults to a sampled lane
(generated inputs); a finite map makes an exhaustive **Lean** lane available to close a
bounded property with `by decide` when the handoff selects it.

No compiled reviewer, no upstream prompt tree, no forge, no orchestrator. Drop the pack into
any agent session's skill directory and it runs.

## Contents

| path | role |
|---|---|
| `SKILL.md` | skill entry point: when to use, the two procedures, packing rules, pitfalls |
| `references/review-core.md` | static protocol: modes, Phase 1, Phase 1b, Phase 2, disposition, carried list, return shape |
| `references/false-positive-guide.md` | applied in Phase 2 before a concern is reported |
| `references/property.md` | falsification protocol for unverified premises, with the sampled and exhaustive lanes |
| `references/lean.md` | exhaustive lane: when to use or skip, procedure, environment, acceptance, worked shapes |
| `references/lean-handoff-example.md` | worked handoff and return shape for the exhaustive lane |
| `references/report-consumer-validation.md` | how a caller validates a report parser against its own reports |
| `references/domain-notes.md` | optional domain notes format |
| `templates/handoff-review.md` | review hop handoff, carries the `protocol:` line |
| `templates/handoff-property.md` | property hop handoff (both lanes), carries the `protocol:` line |
| `tests/accept_pack.py` | acceptance gate: version consistency, referenced files, host independence, Phase 1b completeness and item numbering, previous-report plumbing, two-procedure surface, the Lean lane contract, production firing conditions, the fix-predicate pair, report-consumer validation, the README invocations |
| `tests/test_pack.py` | stdlib contract and mutation tests: throwaway pack copies, asserted `STAGE:` diagnostics, version-literal boundaries |

## Install

Copy the pack so that the agent's skill loader sees `SKILL.md` at the pack root, e.g.

```
<agent skills dir>/eview/            # this repository's contents
  SKILL.md
  references/…
  templates/…
```

A symlink to a checkout works too and keeps one source of truth.

## Run

1. Write a handoff from `templates/handoff-review.md` (or `handoff-property.md`) with the
   `protocol:` line intact and the **absolute path** of the previous round's report.
2. The worker loads `SKILL.md` and follows the named procedure. A review return contains
   `## Findings`, `## Carried / unresolved` and `## Unverified premises`. A property return
   uses the selected lane's schema below.
3. A clean review verdict requires no findings **and** an empty carried list. Anything carried
   remains unresolved for the caller to disposition.

### Property, exhaustive lane

The property procedure picks its lane before writing anything:

- **sampled** (default) — generate inputs, hunt a counterexample, shrink it, classify it.
  "No counterexample" is sampling, not assurance.
- **exhaustive** — the diff contains a finite map (a setting or permission table, an
  identification function, a state machine, a normalization, or a classification). Load
  `references/lean.md`, formalize the map outside the target repository with the target
  read-only, and close the properties with `by decide`.

The exhaustive return is not the sampled schema: it carries a property / result / theorem
table, each counterexample **with the production condition under which it fires**, a fix
predicate proved as a pair (the counterexample is gone **and** the legitimate cases still
pass), the limits, and the generated `.lean` artifact path. Skip the lane with `SKIPPED` and
a reason when there is no finite executable map or no implementation, when the theorem would
be trivially true, or when the question is a design judgement. An exhaustive-only return does not append the sampled
lane's sampling disclaimer: it may state theorem closure over the transcribed bounded domain,
while explicitly stopping short of claiming that the source system is verified. The theorem
closes only the stated property over the transcribed bounded domain; it does not verify the
source system. A skipped exhaustive-only return carries `status=SKIPPED`, the reason and
evidence, and notes; it needs no theorem table, Lean artifact, or build result.

## Changing the protocol

- Bump `version:` in `SKILL.md` and the `protocol:` line in **both** templates in the same
  change; every other file refers to "the `protocol:` line from the handoff" and never
  restates the literal.
- Run the gate before you hand the pack to anyone:

```bash
python3 tests/accept_pack.py          # exit 0 = PACK_OK, else one STAGE: C<n> line per gap
python3 -m unittest discover -s tests -p 'test_*.py'     # contract + mutation tests
```

The tests are prompt **contract** tests: they check that the protocols, templates and docs
state the required rules, and that mutated throwaway copies of the pack are rejected for the
intended reason. They are not an LLM efficacy benchmark and say nothing about how well any
model reviews or proves.

## License

[MIT](LICENSE).
