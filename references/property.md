# Property falsification

Hunt counterexamples in the changed code. Infer intended properties from evidence, write
property-based tests for them in a writable throwaway tree, execute, shrink, and classify.

The product is the falsification report, not new tests in the repository.

Two lanes share this protocol. The **sampled** lane generates inputs and hunts a
counterexample; the **exhaustive** lane enumerates a finite domain and shows that no
counterexample exists. Pick the lane before writing anything (see *Lane selection*).

## Preconditions

- A throwaway copy of the head revision. Never execute in the reviewed tree.
- The specification or interface documents. Without them, properties are guesses.
- The previous report, when the handoff names one (see *Previous report* below).
- **Sampled lane:** the repository runtime and a property library must be runnable in the
  throwaway. The repository's own suite need not pass; a failing existing suite is not a
  reason to carry the pass. If the sampled environment blocks execution, carry that lane.
- **Exhaustive-only lane:** a Lean toolchain and readable source are sufficient. It does not
  require the repository runtime or a property library unless they are used to validate the
  transcription. If Lean itself is unavailable, carry that lane rather than the sampled one.

## Previous report

The handoff names one **absolute** path on its `Previous report` line. Resolve that file
alone: relative paths and directories are not resolved, and no earlier report is searched
for in the repository, the run directory, the forge, or git history. If the file exists,
read it before identifying properties — it supplies the prior round's premises, its
carried items, and any property the prior pass left open or judged sampling-only. If it
does not exist, there is no previous round: proceed without it, state that in `## Notes`,
and do not infer a previous round from commit messages or history. When the report exists,
`## Notes` records each of its unverified or carried items and whether this pass
reproduced, refuted, or left it open.

## Lane selection

Run a finite-map test on the diff first. If **any** of these is present, the exhaustive lane
is available:

- a setting or permission table (value → mode / permission / behaviour);
- an identification or resolution function (input → exactly one target);
- a state machine (state × event → state);
- a normalization or equivalence (string → string);
- a classification (input → one of a finite set of classes).

Then apply the skip test: no finite executable map or no implementation in the diff, a theorem
that would be trivially true, or a question that is a design judgement. Any of those means
`SKIPPED` with the reason.

Honor the handoff's lane token:

- `LANE=sampled` runs only the sampled lane;
- `LANE=exhaustive` applies the finite-map and skip tests, then runs the exhaustive lane or
  returns `SKIPPED`; it does not require a sampled pass;
- `LANE=auto` applies the tests and selects exhaustive for a qualifying finite map, sampled
  otherwise. It may run both when a finite map and a separate unbounded surface both matter.

Without a token, the sampled lane is the default. Both lanes may run on the same diff; the
exhaustive lane does not replace the sampled one for an unbounded domain.

## Procedure

### 0. Environment

Create the throwaway from the reviewed revision (an archive or a clone) and keep the
repository's own directory name as the leaf. Then set up only the selected lanes:

- For `LANE=sampled`, install the repository runtime plus a property library (Hypothesis for
  Python, fast-check for JS/TS) and record versions.
- For `LANE=exhaustive`, initialize the Lean project outside the target repository and record
  the Lean toolchain. This lane does not require a property library or repository runtime.
- For `LANE=auto`, follow the lane selection result; set up both environments only when both
  lanes will actually run.

If one selected lane cannot run, stop and carry that lane — do not sink or falsely block the
other lane.

### 1. Identify properties

Start from evidence: specification, docstrings, comments, type hints, existing tests,
usage. Keep only properties you are confident are **intended**. Prefer 3–8 high-signal
properties to a long list of weak ones. If none are valuable, say so and stop.

Forbidden: a property derived from the implementation alone. Restating the same branches
and constants adds no detection power.

Useful shapes:

- round-trip — `decode(encode(x)) == x`, `parse(format(x)) == x`
- inverse pairs — add/remove, push/pop, create/destroy
- optimized vs reference implementation
- idempotence `f(f(x)) == f(x)`; commutativity
- diff builder — apply the produced update, rebuild, expect no further change
- preservation — items outside the managed set are unchanged and keep their order
- invariants — `len(filter(x)) <= len(x)`; `set(sort(x)) == set(x)`
- confluence — application order does not matter
- metamorphic — a stated relationship between `f(x)` and `g(x)`
- stateful — a call sequence preserves an invariant or agrees with a model; the model must
  be a plain list/dict, never a reimplementation of the logic under test

### 2. Check usage

Read how the codebase actually calls the code: which input kinds occur, with which guards.
The specification is authoritative; usage corrects misunderstandings.

After step 2, the sampled lane continues through steps 3–4. The exhaustive lane skips those
sampled-only steps and continues at *Exhaustive mode (Lean)*.

### 3. Write sampled tests (sampled lane only)

Write in the throwaway, following the repository's test conventions. Sound (only inputs
the code can be called with) and mostly-complete (~90% of the real input domain).

- Constrain strategies only where the code requires it. No gratuitous `max_size`, no
  filtered domains that avoid the interesting inputs.
- Set `deadline=None` (or a generous value) on Hypothesis tests.
- Bound example counts (default ≤ 500 per property) and record them.
- Record seeds for every failure.
- Keep a few clearly named test files.

### 4. Run, reflect, shrink, classify (sampled lane only)

On failure, decide before claiming:

- **REAL-BUG** — the input is in the documented domain and the code violates an intended
  property.
- **TEST-BUG** — the input violates a documented assumption, or the property misread the
  intended domain. The common case for a surprising failure is a wrong test; refine at
  most twice, then drop it with a note.
- **SPEC-AMBIGUITY** — the spec does not settle the behaviour. A question for the author.

For a genuine bug: shrink to the minimal falsifying input, pin it as `@example(...)`, save
the failing test, seed, and a log excerpt. Only claim a bug you can justify.

## Exhaustive mode (Lean)

Sampling cannot prove absence. In this lane the finite map is formalized and the properties
are closed with `by decide`, so the report can say that no counterexample exists in the
bounded domain — or exhibit one.

- Protocol: `references/lean.md` (required for this mode). Worked handoff and return shape:
  `references/lean-handoff-example.md`.
- Same lane, same throwaway workspaces: the model is written outside the target repository
  and the target is read-only. Do not add `.lean` files or `lake` projects to the repository.
- The map is transcribed from the code, not from the review prose, and each transcription
  keeps its `file:line` provenance. A transcription that changes the code's meaning proves
  nothing.
- Acceptance differs from sampled mode. When the lane executes, the return carries:
  1. a **property / result / theorem table** — one row per property, with the theorem name
     that closes it and whether it holds, produced a counterexample, or was skipped;
  2. each **counterexample** with the minimal input and the **production condition under
     which it fires** (the input bound, the window width, the call order that reaches it);
  3. a **fix predicate** proved as a pair: the counterexample is removed **and** the
     legitimate cases still pass — disabling the behaviour is not a fix;
  4. the limits — which domain was bounded and how, and what was not checked (infinite
     domains, external APIs, order dependence);
  5. the generated `.lean` artifact's absolute path and the `lake build` result.
- Skip the mode entirely when there is no implementation (design-doc-only diff), when the
  theorem would be trivially true, or when the question is a design judgement. A trivially
  true theorem is lane misuse: say `SKIPPED` and give the reason.
- A skipped exhaustive-only pass uses the skipped return schema below. It requires no theorem
  table, `.lean` artifact, or build result because no formalization ran.

## Return schema

### Sampled-mode return

Header (a combined sampled + exhaustive run uses this header with
`lane=sampled+exhaustive`):

```text
pack=eview/property | protocol=<value of the handoff's protocol: line> | repo=<name> | range <base12>...<head12> | model=<id> | wall <Nm> | lane=sampled | seeds <list> | examples <n/...>
```

`## Findings` — per item: id, classification, severity candidate with rationale,
`file:function`, property text, why it is believed intended, minimal repro (test snippet,
shrunk input, command, log excerpt, same-seed rerun stability), confidence and what would
raise it.

`## No-counterexample summary` — per property: text, examples tried, seed, result.

`## Carried / unverified` — environment-blocked or unrunnable properties and what would
settle them.

`## Notes` — versions, artifact paths, prior-report reconciliation, and the mandatory line:

- the previous report's status: its absolute path and, for each unverified or carried item
  it lists, whether this pass reproduced, refuted, or left it open — or, when the handoff
  names none or the named file does not exist, that there was no previous round;
- the mandatory line:

> No counterexample found is sampling, not assurance.

### Exhaustive-mode return

An exhaustive-only run uses a proof-scoped header; it does not carry meaningless `seeds` or
`examples` fields:

```text
pack=eview/property | protocol=<value of the handoff's protocol: line> | repo=<name> | range <base12>...<head12> | model=<id> | wall <Nm> | lane=exhaustive | domain=<bounded domain>
```

These sections replace `## No-counterexample summary`:

`## Property / result / theorem` — the table:

```text
| property | result | theorem |
|---|---|---|
| <text> | holds / counterexample / skipped | `theorem_name` |
```

`## Counterexample` — the minimal input, the production condition under which it fires, and
the theorem that exhibits it. `none` when every property holds, with the bounded domain
restated.

`## Fix predicate` — the predicate, the counterexample gone, and the legitimate cases that
still pass, each as a proved pair. Omit only when no counterexample was produced.

`## Limits` — the bounded domain, what was not formalized, and what the lane therefore does
not claim. The theorem closes only the stated property over the transcribed bounded domain;
it does not verify the source system.

`## Notes` — as above, plus the `.lean` artifact's absolute path and the `lake build` tail.
The sampled-lane mandatory line applies when sampling also ran. Do not append the sampling
disclaimer to an exhaustive-only return.

### Skipped exhaustive return

When `LANE=exhaustive` reaches a skip condition before formalization and no sampled lane ran,
return this schema instead:

```text
pack=eview/property | protocol=<value of the handoff's protocol: line> | repo=<name> | range <base12>...<head12> | model=<id> | wall <Nm> | lane=exhaustive | status=SKIPPED

## Skipped
reason: <no finite executable map | no implementation | trivially true | design judgement>
evidence: <file/range inspected>

## Notes
<previous-report reconciliation and limits on the skip decision>
```

Do not emit a property / result / theorem table, `.lean` artifact, or `lake build` result: the
lane did not execute. Do not append the sampling disclaimer. If sampling also ran, use the
sampled or combined schema instead and record the exhaustive skip in `## Notes`.

## Pitfalls

- Sampled lane: missing property library → install it in the throwaway; do not fall back to
  example tests. It is not a prerequisite for an exhaustive-only lane.
- Restricted sandboxes need cache directories inside the writable tree.
- Network-restricted environment → carry the item; do not stub the dependency to make a
  test run.
- Flaky failures → record the seed, re-run pinned, bound example counts.
- Never edit the reviewed tree, never add generated tests to the repository, never weaken
  a true property to make it pass.
- Exhaustive mode covers only a finite, pure map. When unbounded behaviour is also in scope,
  run the sampled lane too; an explicitly exhaustive-only handoff does not require it. Say
  which domain you bounded and how.
- A counterexample that cannot fire in production is not a finding. State the firing condition or
  drop it.
- "Uniqueness holds" is not "identity holds". State the gate's coverage: what it prevents and
  what it does not (usability, ownership, freshness).
- A fix proved only to remove the counterexample is half a proof: the pair with the
  legitimate cases is what keeps a review from recommending a regression.
