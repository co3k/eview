# Lean exhaustive lane

Formalize a **finite map** from the diff and close its properties with `by decide`. Where
dynamic falsification (`property.md`) generates inputs and hunts a counterexample, this lane
enumerates the domain and shows that no counterexample exists. The claim is stronger and
the scope is narrower.

## When to use it

Use it when the diff contains a finite map in one of these shapes:

- **A setting or permission table** — value → mode / permission / behaviour (an `allowed`,
  `default` or `fallback` table)
- **An identification or resolution function** — input → exactly one target (name matching,
  user lookup, key resolution)
- **A state machine** — state × event → state (approval flow, triage, job stage)
- **A normalization or equivalence** — string → string (character width, case, whitespace,
  synonyms)
- **A classification** — input → class, with the per-class rules written as a table

## When to skip it

- There is no finite executable map or no implementation (a design document, prose,
  message-string-only change, or dependency pin)
- **The theorem would be trivially true** (a restatement of constant definitions)
- The question is a judgement about meaning (design, naming, UX, prose)

Skipping is not a failure: record `SKIPPED` with the reason why formalization has no value.
Manufacturing trivial theorems is lane misuse and costs the review its credibility.

## Procedure

1. **Extract the target function or table** — do not load the whole application. Use a
   language-native parser or AST when available, or make the smallest compilable slice that
   preserves the implementation's meaning. Keep the extraction read-only and record its
   `file:line` provenance; this applies equally to Python, JS/TS, Rust, Go, and other sources.
2. **Identify the finite domain** — enumerations, character ranges, small state sets. If the
   domain is infinite (an arbitrary-length list, free-form text), bound it by length and
   write the bound into the report.
3. **Translate the map into Lean** — keep the original `file:line` in a comment. **Do not
   change the code's meaning**: transcribing from the review prose instead of the code is
   where this lane goes wrong.
4. **Turn the properties into theorems** — table soundness (the default and the alternative
   values are in the allowed set), totality, injectivity, uniqueness, order preservation,
   fail-safety, idempotence.
5. **Close them with `by decide`.** A goal that will not close means either (a) the domain is
   not finite or (b) the property is false.
6. If it is false, produce the **minimal counterexample**.
7. **Write the fix as a predicate and prove the pair**: the counterexample disappears **and**
   the legitimate cases still pass.
8. Report the **property / result / theorem** table, the counterexample, the fix, and the
   limits.

## Environment (Lean 4 core only; no Mathlib)

```bash
elan toolchain install leanprover/lean4:v4.23.0 && elan default leanprover/lean4:v4.23.0
lake new <proj> lib && cd <proj> && lake build
```

- `#guard` is a compile-time test (the build fails when it is false); use it to embed the
  examples from the specification.
- `#eval` / `IO.println` emit test vectors for the implementation's own tests.
- `Finset` comes from Mathlib. With the core only, enumerate with an explicit list.

## Pitfalls

- Constructor shorthand (`.foo`) does not resolve when the expected type is a bare
  constant. Write it fully qualified (`State.new`).
- `\"` cannot appear inside `s!"{...}"`. Concatenate the strings instead.
- `decide` hits the recursion depth limit on counterexample search. Set
  `set_option maxRecDepth 20000`.
- **A counterexample that cannot fire in production is not a finding.** State the firing
  condition (for example: the window width is 4 and the input is split on whitespace, so
  the case does not fire today; raise the window and it fires).
- "Uniqueness holds" is not "identity holds". State the gate's **coverage** — what it
  prevents and what it does not (usability, ownership, freshness).
- The theorem closes only the stated property over the transcribed bounded domain; it does
  not verify the source system.

## Acceptance

When the lane executes:

- A property / result / theorem table exists.
- Every counterexample carries the production condition under which it fires.
- The fix is a predicate proved as a pair: the counterexample is gone **and** the legitimate
  cases still pass.
- The limits are stated: what was not checked (infinite domains, external APIs, order
  dependence).
- The generated `.lean` artifact's absolute path and the build result are recorded.
- The theorem closes only the stated property over the transcribed bounded domain; it does
  not verify the source system.

When the skip test fires before formalization, use the skipped return below instead. The
theorem table, `.lean` artifact, and build result are not required because the lane did not run.

## Skipped return

Echo the handoff's `protocol:` value in the property header with `lane=exhaustive |
status=SKIPPED`, then emit:

- `## Skipped` — the exact reason and the file/range evidence for it;
- `## Notes` — previous-report reconciliation and limits on the skip decision.

Do not emit theorem results or a Lean artifact. Do not append the sampling disclaimer unless
the sampled lane also ran; in that combined case, use the sampled schema and record this skip
in its notes.

## Worked shapes

Use these neutral forms as starting points for a transcription; replace each example with the
actual code and provenance from the reviewed diff.

| shape | target | useful proof question |
|---|---|---|
| classification × mode table | setting value → execution mode | Are all defaults and alternatives allowed, and does an unknown value fail safely? |
| identification function | key + label → one record | Does uniqueness imply a valid selection, or can one unusable record still win? |
| state machine + resolution rule | event → request record | Which stale or repeated events does the guard prevent, and which can still pass? |
| normalization / round-trip | source alphabet ↔ normalized alphabet | Is length preserved, does the round-trip hold on the bounded range, and which code point breaks it? |
| workflow state machine | start → done → evidence → verdict | Is an empty transition among the legal moves, and does the fix remove only that transition? |
| ledger invariant | append of start/finish records | Is the assertion sufficient for every reachable state and necessary for the invariant? |
| naming rule | prefix + role → identifier | Uniqueness of what: identifier, role, or work item; can a prefix change repeat work? |

### Choosing a shape (quick reference)

- A table exists → "are the default and alternative values in the allowed set", "which cell
  is the exception"
- A function selects one → not "is it unique" but "**after** it is unique, is the selection
  valid"
- A guard exists → "what does it prevent, and **what does it not prevent**" (coverage)
- A conversion exists → "does it round-trip", "**which characters break it**", as one point
- A loop exists → "is there an empty move among the legal moves"
- A ledger exists → "is the assertion sufficient (does every reachable state satisfy the
  invariant)" plus "is it necessary (remove it and exhibit the break)"
- A name or ID exists → "uniqueness **of what**"

### Pitfalls measured in practice

- Short names such as `nm` can collide with a Lean token. Use a specific name (`attemptName`).
- A `structure`'s `⟨a, b⟩` does not always elaborate. Provide a constructor function
  (`def mkA`) and write `name (mkA 1 4)`.
- `String` is hard to reduce with `decide`. Abstract to `Nat` (encode the pair as
  `prefix * 100 + role`) and the proof closes.
- Mutually recursive helpers belong in top-level `def`s, not in `where`.
