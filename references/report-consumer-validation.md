# Validating review-report consumers

These are caller-integration checks, not changes to the review or property procedures.

- Match the consumer to the report's actual `protocol:` schema before interpreting a parsed result; an unsupported schema must refuse rather than default to an empty finding list.
- Reconcile every actual finding row, severity/location/function field, carried item and declared disposition against the parser's output; a zero exit or empty parsed list cannot overrule nonempty raw findings or `REQUEST_CHANGES`.
- Keep raw row count distinct from deduplicated issue count, because two independent reports may identify the same issue under different identifiers.
- Exercise any replacement parser or bounded explicit ledger with both healthy/empty and deliberately nonclean fixtures; a consumer that silently drops the nonclean rows is not qualified.
- Exercise sampled, exhaustive, and `SKIPPED` property fixtures; a documented skip must remain distinct from a clean proof, a counterexample, and a malformed report.
- Preserve the incompatible parser's exact output as rejected evidence and retain the full raw reports; never rewrite a failed merge as clean or weaken review criteria to accommodate it.
- Keep a local consumer repair separate from global parser redesign, and avoid changing procedure/template files already pinned by active hops merely to fix one caller's interpretation.
