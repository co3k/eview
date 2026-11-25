# False-positive guide

Apply in Phase 2 to every concern before it becomes a finding.

1. **No traced path, no finding.** If you cannot name the input and the code path that
   reaches the defect, it is a premise or a carried item.
2. **Do not restate the implementation as a defect.** "This code does X, so X may not be
   intended" is not evidence. Cite the specification, an interface promise, a caller
   contract, or an established convention.
3. **Absence of a test is not a finding by itself.** Report missing coverage only when
   the changed behaviour is unverified and the omission hides a plausible failure.
4. **Style, naming, and structure are not bugs.** Note them separately, explicitly
   labelled not-a-bug, or omit them.
5. **Do not invent external facts.** Deployment state, secret contents, live data shape,
   and operator behaviour are carried items unless the repository proves them.
   - Scope: this concerns facts **outside the tree**. What the tree declares — an option,
     flag, config key, documented input, or documented behaviour — is read from the tree
     itself; its lack of a consumer is a doc/contract finding (review-core, Disposition).
     Whether anyone supplies the input is still an external fact: it is a premise, not a
     reason to drop the mismatch.
6. **Do not double-report one mechanism.** Deduplicate by cause, not by phrasing. If
   several call sites share a defect, report the mechanism once and list the sites.
7. **Do not upgrade severity for emphasis.** Severity follows impact and reachability.
8. **Do not drop a concern because the fix would be large.** Size is not a disposition.
9. **Do not treat the author's explanation as proof.** Verify it in the code; an
   explanation that contradicts the implementation is itself a finding.
10. **Do not weaken a true property or finding to make a check pass.**
11. **Prior-round fixes (Phase 1b items 8, 9a, 9b, 10, 11 and 12).** Item 11 covers state with
    a lifetime: a reset, a dedupe set, an idempotency key. A fix being present is not
    evidence that it works. Do not drop a concern because the fix "looks like the same
    change elsewhere"; name the input where pre-fix and fixed behaviour differ (item 9a),
    and check that the evidence for it is not the code's own output (item 9b). Trace the
    changed call chains for a short-circuit that skips a required step (item 10). A fix's
    own test passing is not evidence when that test passes without the fix. Ambiguity about
    the intended reading is stated as a question, never resolved in the fix's favour.
    For that state, a passing run rate over rounds is not evidence that the state is scoped
    and consumed as intended: name one input whose second use in the same round behaves
    differently from the first, and the unit (request, item, round, process) that owns it.
12. **A judge reading its own subject (Phase 1b item 12).** Do not drop a concern about a
    check that reads the text of its own subject on the ground that "the rule is
    documented" or "the check passes". Which field the check reads, and what writes that
    field, are visible in the code: that is not an external fact (item 5). A doc that
    declares a rule independent of its subject, while the code reads the subject's own
    prose, is a doc/contract mismatch on the code's side, not a defence of the rule.
