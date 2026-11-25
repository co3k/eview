# Static review protocol

Deep correctness review of a commit, range, or PR. This is not a style pass and not a
quick sanity check. Assume the change has defects until each hunk is proven correct.

## Preconditions

- The reviewed tree is readable. Do not modify it.
- The mode is resolved (see Modes). In range mode you know the range; for a PR,
  `BASE...HEAD` (three-dot) unless the merge-base is the base tip. Full-tree mode needs
  no range.
- Full function bodies are available, not only diff fragments.
- The previous report is resolved from the handoff's `Previous report` line, which names
  one **absolute** path. Relative paths and directory paths are not resolved and not
  searched. If the file exists, read it before Phase 1b: it is the input for items 8 and 9a
  and for the carried list. If it does not exist, there is no previous round — record
  item 8 and 9a as `N/A` on that ground and do not look for an earlier report anywhere
  (repository, run directory, forge, or git history). "Previous report" means that one
  file, no other. Item 9b, item 10, item 11 and item 12 do not read the previous report
  and still apply.

## Modes

Choose the mode from the handoff's Mode line.

- **Range mode** (default): commits oldest to newest, per-commit diff analysis as in
  Phase 1.
- **Full-tree mode**: no diff. Enumerate the units under review: modules, packages, entry
  points, plus the declared focus paths. Read each unit's definitions, then apply the Phase 1
  dimensions and Phase 1b items against the tree as it stands.
  - A finding describes a defect in the current state, not one "introduced by this patch".
    `preexisting` is meaningless in this mode; do not claim it.
  - Phase 1b items 1, 2, 8, 9 and 10 are `N/A` unless a diff was also supplied — or, for
    items 8 and 9a, an artifact of the previous round, such as its previous report. Record
    them as `N/A` with that reason; do not skip them silently.

If the Mode line is missing, use range mode. If no range is resolvable, use full-tree mode
and say so in the return.

## Phase 1: Collect

The units are the commits, oldest first, in range mode, and the enumerated units (see
Modes) in full-tree mode. For each unit:

1. Read the whole diff hunk by hunk.
2. Load the full definition of every modified function, plus its callers and callees.
3. Load the schema/type definitions of external data the change reads or writes.
4. Record every concern. Do **not** verify, downgrade, or discard yet.

Analysis dimensions, all of them, even after finding a bug:

- **Intent** — does the implementation match what the commit message claims; breaking
  interface changes; comments and interface text that overstate behaviour.
- **Correctness** — branch/loop/error-path tracing; null and uninitialized values;
  off-by-one; unchecked return values; tests updated with behaviour.
- **Callers** — broken call sites; new error conditions propagated and handled.
- **Resources** — acquire/release imbalance on every path; cleanup skipped on errors;
  async or deferred work without tracking or cancellation.
- **Concurrency** — shared mutable state; stale captures.
- **External systems** — values from different sources compared without proving the
  same kind and normalization; assumed response schema; long-lived credentials.
- **Security** — injection at trust boundaries; unvalidated input reaching sensitive
  operations; removal of existing authn/authz/validation/rate limits.

## Phase 1b: Targeted second pass

Re-read the diffs. Do not rely on Phase 1 notes. Add new concerns for each item.

Answer every item 1–12 in the return. An item that cannot apply is recorded as `N/A` with
the reason, never omitted.

Items 8 and 9a read the previous report named in the handoff. Without it there is no
previous round: both are `N/A` ("no previous report at the handoff path"), and the return
does not search for one. Item 9b does not read the previous report and still applies: even
when item 9a is `N/A`, record what would count as an oracle under 9b. Item 10 applies
whenever a diff was supplied; with no diff it is `N/A` with that reason.

1. **Security control removal** — scan every removed line for authn, authz, validation,
   rate limiting; check every handler and middleware registration.
2. **Fix completeness** — for a claimed fix, find every path with the same pattern and
   confirm the fix is present in each. Do not trust the commit message. For a fix from a
   previous round, items 8a and 9a apply to it as well.
3. **Cross-system identifier comparison** — every set/map/equality across values from two
   external sources; confirm both sides normalize the same way.
4. **Unvalidated external response fields** — every field access on an external payload;
   confirm existence and type are checked.
5. **Identifier flow** — every place a value from one source meets another source or user
   input: equality, `in` lists, filters, joins, lookups, and generated query text. Per
   pipeline stage (input parsing, selection, join/enrichment, post-join filter), record
   source, field, **value kind** (email vs login vs display name, id vs object id, host vs
   FQDN), and normalization. Then:
   - Kinds must be identical, not merely normalized alike. A shared column name does not
     establish a shared kind. Unknown kind is a premise for item 7.
   - For each documented input kind × data source, name the comparison serving that cell.
     An empty cell is a concern: that input silently yields nothing.
   - If input is resolved to a canonical id, every other filter must run **after** that
     resolution.
   - If a stronger unique id exists on both sides but the match uses a weaker key, that is
     a mis-attribution risk; check the confidence the result claims.
6. **Operator semantics** — enumerate string/match operators in generated or embedded
   query text (`has`, `contains`, `=~`, `==`, `in`, `startswith`, `LIKE`, regex anchors and
   flags, glob). Write the documented semantics from the language spec: whole value vs
   substring vs term/word boundary, case behaviour, empty/null. Then list the column's
   values and confirm each intended match satisfies the operator. A term match does not
   match a substring inside a longer token. If you cannot state the semantics, record a
   premise for item 7 rather than passing it.
7. **Unverified premises** — every assumption about external data: field form, which
   fields are populated, cross-source consistency, key uniqueness, enumerated values, JSON
   key names, non-emptiness of the "latest" row. For each, record how it is verified (a
   realistic test, a fixture/sample, cited documentation). A test asserting generated text
   contains a substring verifies none of these. Unverified → record what breaks if false
   (silent empty result / confidently wrong output / error) and the cheapest check that
   settles it. Carry to Phase 2.
8. **Prior-round fix: under-reach and over-reach** — this item is applied to every fix that
   came from a previous round of review, not to the reviewed change alone; for each such
   fix, do 8a and 8b in that order. A fix with no traceable previous-round concern is
   recorded as `N/A` for this item, and item 9 still applies.
   - **8a Under-reach.** For a claimed fix, find every path with the same pattern and
     confirm the fix is present in each. Do not trust the commit message.
   - **8b Over-reach.** Before reading the fix, write two lists: cases it must now handle,
     and cases the pre-fix code handled correctly. For each added filter, exclusion, or
     guard, enumerate what else satisfies it. Trace both lists through the fixed code; a
     test for the reported case alone is insufficient. State ambiguity rather than adopting
     the fix's reading.
   - **Worked example.** Reported: "`is_admin` matches any user whose login contains
     `admin`." The fix changes `login LIKE '%admin%'` to `login = 'admin'`.
     - 8a: list every place that matches `admin` — the login lookup, the group-membership
       check, and the audit-log filter. Under-reach is the second site still using the
       substring match.
     - 8b: list 1 — every case the fix must now cover: a real operator named `Admin`,
       case variants of `admin`, and the service role `admin@corp`. List 2 — cases the
       pre-fix code handled correctly: the role `sysadmin` and the user `admin2` never
       matched, and must still not match. Trace list 1: if the comparison became
       case-sensitive, `Admin` no longer matches — the fix over-reaches. Trace list 2: the
       fix is correct there. The fix's test covers `admin2` only, so both misses pass
       unseen. The question for the author is what the comparison is now and whether the
       group-membership check was updated.
9. **Discriminating power** — for every fix from a previous round, ask what evidence would
   distinguish the fixed behaviour from the pre-fix behaviour before calling it fixed.
   This item has two sub-items: **9a** (the input, where it is exercised, the verdict) and
   **9b** (the oracle check). Answer both; when there is no prior-round fix, 9a and 9b are
   each `N/A` with that reason.
   - **9a Discriminating input.** Name the input or state on which pre-fix and fixed code
     return different results, and confirm that input is exercised: a test, a fixture, or
     the fix's own diff. A test that passes before and after the fix is not evidence;
     neither is one that only exercises paths both versions run identically.
     - Name the check that would fail if the fix were reverted.
     - If no such input can be named, the fix may not address the reported defect at all.
       Reopen the concern under item 8a, and record a premise under item 7 when the answer
       depends on external data.
     - Record for each prior-round fix: the discriminating input, where it is exercised,
       and the verdict — discriminated, undiscriminated, or premise.
   - **9b Oracle.** When the discriminating input comes from a test, fixture, or the review's
     own instrumentation, that source must not be an oracle for the question it settles:
     it must not be the producer of the value under test, and it must not derive the value
     from the string it judges. A test that builds its expectation by calling the code
     under test, or by re-running the same helper that produced the output, compares the
     code with itself; it cannot be the witness that the fix works — same input, same
     output from both sides is then undiscriminated, not confirmed. Prefer an expectation
     written independently (a literal, a hand-traced value, a documented example) or a
     fixture captured outside the code under review. Record for each prior-round fix where
     the expectation came from and whether it is self-referential.
10. **Call order and short-circuit** — for every changed call chain, trace the order of
    calls from the entry point down: what is evaluated first, what returns before the rest
    runs, and which side effects an earlier return skips (validation, cleanup, registration,
    logging, resource release). Check `and`/`or`, `&&`/`||`, early `return`/`continue`/
    `break`, `?.`, `??`, and lazily called callbacks in the changed lines. For each, ask
    whether the skipped step was required on that path, and whether a value used after the
    branch is set only on the branch that ran. A fix that moves a call before its guard, or
    behind a short-circuit that newly fires, is item 8b on that path.
11. **Scoped, consumed state — resets and idempotency keys** — for every flag, counter,
    dedupe set, or idempotency key the change adds, clears, or relies on, trace its
    lifetime in the code and state three things. (a) **Scope**: what unit owns the state
    — one request, one item, one round, one process, an external store — and at which
    point it is created, cleared, and read. Is a "reset at the start of the round" in
    reach of a request that runs later in that same round? Is it cleared only for some
    rounds or some items? (b) **Consumption**: whether the second use in the same scope
    is suppressed (key hit, dedupe-set entry, flag already cleared) or passes; name the
    key, its fields, and their normalisation. If a retry, replay, or second round is meant
    to proceed, state on which input it does and how that input differs from the one
    suppressed. (c) **Evidence**: the case where the two uses must differ — an independent
    expectation, not a test that only replays one use, and not a pass rate quoted from a
    run whose input the tree does not contain. A reset scoped per process or per run while
    the behaviour under review is per round (or the reverse) is a scope mismatch; an
    idempotency key that the same reset also clears makes the retry it was meant to guard
    indistinguishable from the original. Items 8, 9a and 9b apply when a fix touches such
    state; item 10 applies to where the reset is called relative to the guard it changes.
    This item reads no previous report and applies without one.
12. **A judge reading its own subject — the rule and the text it judges** — for every
    check that decides a pass or a refusal, trace both sides to a file: what the check
    **reads** as its material (a title, a why, a task statement, an acceptance line,
    commit message, help text, a ledger field) and what the check **judges** (the
    command it must refuse, the output it must accept, the task it must dispatch).
    Record the source of the material with file and field. The item holds when both
    sides land on the same subject: the lint rule or gate that refuses a command by
    reading a string out of the task that *is* the command ("no commit", "do not
    commit", a quoted flag) decides what to refuse from the text of what it refuses —
    the subject is the judge's own evidence, so the check can only confirm itself. Ask:
    - Is the material the subject, or an independent specification of the subject? Text
      about the subject (a spec, a changelog, a hand-written expected list) is
      independent; the subject's own acceptance of the check is not.
    - Does the check read a field it also writes, or one it derives by the same helper
      that produced the string it judges? That is item 9b applied to code, not only to
      tests.
    - What would the check report if the prose were rewritten (rephrased, negated,
      quoted) but the behaviour were the same? If the verdict moves, the check judges
      the prose, not the behaviour — a wrong-but-confident pass or a false refusal.
    Items 9b and 12 are the two faces of one question: 9b asks whether a test's
    expectation comes from the code it exercises (test oracle); 12 asks whether a
    production check's input comes from its own subject (judge and judged are the same
    artifact). A finding under 12 names the reader (file and function), the field it
    reads, and who writes that field; the reader in the product and the string it
    judges are both in the reviewed tree, so no runtime run is needed to state it.
    This item reads no previous report and applies without one, with or without a diff
    (it is not `N/A` in full-tree mode: the reader and the subject are both in the tree).

## Phase 2: Verify and report

1. Deduplicate concerns across commits.
2. Drop a concern only on one of two grounds: a later commit in the series resolves it, or
   it is disproved under the false-positive guide. Nothing else permits a drop.
3. Apply the false-positive guide, including its pointer for prior-round fixes (items 8,
   9a, 9b, 10, 11 and 12): a concern about a fix's reach, discrimination, or evidence is
   judged by the same grounds.
   In particular, FP-guide item 5 ("do not invent external facts") is a rule about
   provenance, not a ban on documentation concerns: what a file is declared to be, by the
   code or its own text, is visible in the reviewed tree and is not an external fact.
4. Report.

### Disposition

Prove the issue with a concrete path before reporting it. The same rule cuts the other way:
concerns are dropped or downgraded only on grounds verifiable in the material in front of
you. "By design", "as specified", "per the ticket" require reading the specification side
and comparing it with the implementation; where they disagree, report the mismatch.

- An implementation that silently returns nothing, or returns a confidently wrong result,
  for an input kind the interface promises is a finding, not a follow-up.
- A concern you cannot settle goes on the carried list: what breaks if real, what check or
  decision settles it, who decides if known. An unperformed runtime check is open, not
  grounds to drop.
- **Declared contract without a consumer is a doc/contract finding.** "Doc/contract" names
  a declaration on one side — an input, option, flag, config key, or documented behaviour,
  with its file path, flag name, value type, and default — and its reader or executor on the
  other. Both sides are in the reviewed tree; no deployment or operator is needed. Treat the
  declaration as the interface promise (FP-guide item 2) and trace it to its consumer
  (FP-guide item 1):
  - A declared input, option, flag, or config key with no consumer anywhere in the tree is a
    finding: whatever the interface promises never takes effect (silent no-op).
  - Documentation that names an input, option, flag, config key, or default that the code
    does not read, or that describes behaviour the code does not implement, is a finding
    (doc/contract mismatch) on the same ground as an overstated comment under Intent.
    The reverse also holds: a consumer that the documentation never mentions is the same
    mismatch.
  - Name the declaration (file and symbol), the consumer if any, and what the user sees
    when the input is supplied: ignored, rejected, or applied with a different meaning.
    A declaration read only by tests or only by other dead code has no consumer.
  - Not a finding: an input the interface does not promise (private helpers, an option
    another file or package consumes through a documented hook, a key whose absence is
    documented). Key naming and style stay out of it (FP-guide item 4).
  - Whether any deployment actually passes the input is an external fact (FP-guide item 5):
    it sets severity and reachability as a premise (item 7); it does not decide whether the
    mismatch is reported.
- Defensive-programming suggestions need both: untrusted input can reach the code, and the
  code demonstrably fails on it. Wrong-but-confident and silently-empty results are
  correctness findings even when the triggering data cannot be confirmed — mark conditional.
- Runtime-dependent concerns (data volume, timing, external service, configuration) are
  reported as conditional; do not dismiss them because the trigger probably does not occur.
- If the change's purpose depends on a runtime assumption holding, the check that settles
  it is a blocking acceptance item until performed and reported.

Severity: critical / high / medium / low.

### Carried list

The carried list is correctness concerns traced to a concrete path but not reported as
findings — downgraded, deferred pending a check, or held on instruction. It is part of the
output and travels to the next round.

- **Follow-up rounds** re-derive Phase 1b items 5–8, 10, 11 and 12 over the full range; item 9a is
  derived from the prior round's fixes, and item 9b is answered for each of them.
  "Unchanged this round" is not "already reviewed in full"; a question no earlier round
  asked is open.
  Re-check every prior carried item and state its status.
- **Do not re-raise** instructions remove an item only if it could not be proven or was
  adjudicated on grounds you can verify here. Otherwise keep it, marked "held on
  instruction", with the grounds. A scope limit (files or ranges) is followed as given. A
  false positive you disproved yourself is dropped.
- **Protocol line**: every carried item records the `protocol:` line of the round that
  produced it. When a later round runs under a different protocol line, say so and
  re-derive that item under the current rules; do not carry it forward silently.

### Report

- No findings → say so explicitly and still give the carried and premises sections.
- Clean verdict requires no findings **and** an empty carried list.
- Frame issues as questions. Cite function and file, not line numbers. Mark non-bug
  suggestions as not a bug.
- End with **Unverified premises** — each carried item from Phase 1b item 7 (or "none")
  and the check that settles it.

## Return shape

Start the return with the `protocol:` line copied verbatim from the handoff.

One line per finding, with these fields:

```text
id | severity | file:function | concern | evidence | status
```

- `id`: unique within the return.
- `severity`: `critical|high|medium|low`.
- `file:function`: location by file and function, not line number.
- `concern`: the defect, framed as a question.
- `evidence`: the traced path, from input to defect.
- `status`: `reported|carried`.

Then Phase 1b items 1–12, each answered or `N/A` with the reason, followed by the two
summary sections: `## Carried / unresolved` and `## Unverified premises` (say "none" when
empty).

This is the only return shape. One header, one findings list, one answer per Phase 1b
item, one carried section, one premises section — no second schema, no per-section
alternative formats. A round with no findings writes the header, then a single explicit
"no findings" line, then the same sections.
