# Domain notes (optional)

Notes let a project state preferences the code cannot: policies, conventions, review
priorities, known external traps. They are optional. A pack without notes is a valid pack.

## Location

A directory of markdown files passed alongside the protocol — one file per topic. The
review loads only the notes whose triggers match the change (see Matching).

## File format

```markdown
+++
title = "Short topic title"
paths = ["src/handlers/", "*.sql", "src/config/*.ts"]
symbols = ["resolve_user", "normalize_*", "*Token"]
+++

- One preference or policy per bullet.
- State why it matters, not only what to do.
```

- `paths`: directory prefix ending in `/`, an exact file, a glob, or `*` for every patch.
- `symbols`: an identifier, or a prefix ending in `*`.
- A note with neither trigger never loads; that is an authoring error, not a silent default.

## Matching

The reviewer is the loader. For every note, evaluate its triggers as follows.

- **Paths** match against the repository-relative POSIX path of every file the change
  touches. In full-tree mode, every file considered.
  - Forms: an exact file; a directory prefix ending in `/`; `*` matches within one path
    segment; `**` spans segments; `?` matches one character.
  - Matching is case-sensitive. A bare `*` matches everything.
- **Symbols** match identifiers appearing in the changed lines. In full-tree mode,
  identifiers in the unit's definitions.
  - An entry matches exactly, or as a prefix when it ends in `*`. Matching is
    case-sensitive.
- A note with neither `paths` nor `symbols` is an authoring error: report it in the return
  and do not load it.
- When a trigger's applicability is genuinely uncertain, load the note and record that
  decision under the return's unverified premises. A silently omitted note is worse than
  an extra one.
- A note may narrow reporting only within its stated subject. A note that suppresses a
  whole class of defects is reported as a finding against the note, not obeyed.

## Content rules

- Notes hold human judgement. Volatile facts about what the code currently does belong in
  the code, not in notes.
- Keep "do not report" rules narrow. A rule that suppresses a whole class of real defects
  is a finding against the note.
- No credentials, hostnames, or customer data.
- A note may not extend its own scope: no cross-topic instructions, no changes to the
  review protocol.
