#!/usr/bin/env python3
"""Acceptance gate for the eview pack.

Exit 0 only when the pack is complete enough to be handed to someone else and to be
run without a second review lane. Every failing condition prints one line of the form

    STAGE: C<n> <what is missing>

so a failure is diagnosable from this command's own output. Nothing here reads the
run directory; the pack is self-contained.

The pack is two procedures (review + property) and two handoff templates. The property
procedure has a sampled lane and an exhaustive Lean lane; C12-C18 pin the two-procedure surface:
the removed procedure stays removed, the Lean lane is formalized, every counterexample
carries its production firing condition, the fix predicate is proved with the legitimate
cases, and the README's own commands are the ones a reader can run.

Usage: python3 tests/accept_pack.py [PACK_DIR]   (default: the parent of tests/)
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

REQUIRED_PHASE1B_ITEMS = 12
RETURN_SHAPE_FIELDS = ("id", "severity", "file:function", "concern", "evidence", "status")
# A distributed pack must not carry one machine's concrete home layout.
# Structural patterns avoid embedding specific products, hosts, or operators in the gate itself.
PLACEHOLDER_SEGMENT = re.compile(
    r"(?:<[^<>/\\]+>|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|%[A-Za-z_][A-Za-z0-9_]*%)"
)
HOST_PATH_PATTERNS = (
    ("absolute POSIX home path",
     re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users|var/home)/"
                r"(?P<owner><[^<>/\\]+>|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|"
                r"%[A-Za-z_][A-Za-z0-9_]*%|[^/\s`\"',.;:)\]}]+)"
                r"(?=[/\s`\"',.;:)\]}]|$)", re.M)),
    ("root home path",
     re.compile(r"(?<![A-Za-z0-9_])/root(?=[/\s`\"',.;:)\]}]|$)", re.M)),
    ("Windows home path",
     re.compile(r"(?<![A-Za-z0-9_])(?:[A-Z]:[\\/]|/mnt/[A-Z]/)Users[\\/]"
                r"(?P<owner><[^<>/\\]+>|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|"
                r"%[A-Za-z_][A-Za-z0-9_]*%|[^\\/\r\n`\"',.;:)\]}]+?)"
                r"(?=[\\/]|[`\"',.;:)\]}]|$)", re.I | re.M)),
)
# The two handoff templates the pack ships. A missing one is a failure, never a skip.
REVIEW_TEMPLATE = "handoff-review.md"
PROPERTY_TEMPLATE = "handoff-property.md"
REQUIRED_TEMPLATES = (REVIEW_TEMPLATE, PROPERTY_TEMPLATE)
PROCEDURES = ("Review", "Property")
# Both templates carry a previous-report line (a round-over-round contract).
PREVIOUS_REPORT_TEMPLATES = (REVIEW_TEMPLATE, PROPERTY_TEMPLATE)
# Artifacts the two-procedure pack removed; their return is a regression, not a feature.
REMOVED_PATHS = ("references/comprehension.md", "templates/handoff-comprehension.md",
                 "tests/test_comprehension.py", "tests/fixtures/comprehension")
LEAN_PROTOCOL = "references/lean.md"
LEAN_EXAMPLE = "references/lean-handoff-example.md"
CONSUMER_DOC = "references/report-consumer-validation.md"
TEST_FILE = "tests/test_pack.py"
GATE_COMMAND = "python3 tests/accept_pack.py"
TEST_COMMAND = "python3 -m unittest discover -s tests -p 'test_*.py'"
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10}
MAX_DESCRIPTION = 60
# Rules the exhaustive lane exists for, stated in the three files that must agree.
FIRING_RULE = "counterexample that cannot fire in production is not a finding"
IDENTITY_RULE = '"uniqueness holds" is not "identity holds"'
IDENTITY_ACTIONS = ("coverage", "what it prevents", "what it does not",
                    "usability", "ownership", "freshness")
PROOF_SCOPE_RULE = ("The theorem closes only the stated property over the transcribed "
                    "bounded domain; it does not verify the source system.")
PROOF_SCOPE_FILES = ("SKILL.md", "README.md", "references/property.md", LEAN_PROTOCOL,
                     LEAN_EXAMPLE, f"templates/{PROPERTY_TEMPLATE}")
SAMPLED_DISCLAIMER = "No counterexample found is sampling, not assurance."
# Report-consumer rules, each pinned inside the doc that owns them.
CONSUMER_RULES = (
    ("the schema-first refusal", "unsupported schema must refuse rather than default to an "
                                 "empty finding list"),
    ("row-by-row reconciliation", "Reconcile every actual finding row"),
    ("raw count versus deduplicated count", "raw row count distinct from deduplicated issue count"),
    ("both healthy and nonclean fixtures", "healthy/empty and deliberately nonclean fixtures"),
    ("sampled, exhaustive and skipped property fixtures",
     "sampled, exhaustive, and `SKIPPED` property fixtures"),
    ("rejected evidence is preserved", "Preserve the incompatible parser's exact output as "
                                       "rejected evidence"),
    ("a local repair stays local", "Keep a local consumer repair separate from global parser "
                                   "redesign"),
    ("that it is not a third procedure", "not changes to the review or property procedures"),
)


def pack_files(root: Path) -> list[Path]:
    files = [root / "SKILL.md"]
    for sub in ("references", "templates"):
        files.extend(sorted((root / sub).glob("*.md")))
    return [p for p in files if p.is_file()]


def skill_version(text: str) -> str | None:
    front = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not front:
        return None
    found = re.search(r"^version:\s*[\"']?([0-9][0-9A-Za-z.\-]*)[\"']?\s*$", front.group(1), re.M)
    return found.group(1) if found else None


def protocol_version(line: str) -> str | None:
    found = re.search(r"([0-9]+\.[0-9]+\.[0-9]+[0-9A-Za-z.\-]*)", line)
    return found.group(1) if found else None


def version_literal_pattern(want: str) -> "re.Pattern[str]":
    """A restated version: `eview/N.N.N`, or the bare literal.

    The bare literal may be followed by sentence punctuation ("version 0.4.0.") but not by a
    word character or a further dotted number, so a longer, unrelated version (`0.4.0.1`,
    `0.4.01`, `10.4.0`) is not a match.
    """
    return re.compile(r"eview/[0-9]+\.[0-9]+\.[0-9]+|(?<![\w.])" + re.escape(want) + r"(?!\w|\.\d)")


def c1_version_consistency(root: Path) -> list[str]:
    problems: list[str] = []
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    want = skill_version(skill)
    if not want:
        return ["SKILL.md frontmatter has no `version:` line"]
    tdir = root / "templates"
    for name in REQUIRED_TEMPLATES:
        if not (tdir / name).is_file():
            problems.append(f"templates/{name} is missing")
    templates = sorted(tdir.glob("*.md"))
    if not templates:
        return problems + ["templates/ has no handoff template"]
    for tpl in templates:
        lines = [l for l in tpl.read_text(encoding="utf-8").splitlines() if l.lower().startswith("protocol:")]
        if not lines:
            problems.append(f"{tpl.name} has no `protocol:` line")
            continue
        if len(lines) > 1:
            problems.append(f"{tpl.name} has {len(lines)} `protocol:` lines, expected exactly one")
        got = protocol_version(lines[0])
        if got != want:
            problems.append(f"{tpl.name} protocol line says {got!r}, SKILL.md says {want!r}")
    # The policy sentence must count the places correctly: frontmatter + one line per template.
    expected_places = 1 + len(templates)
    found = re.search(r"lives in exactly\s+([A-Za-z]+|\d+)\s+places", " ".join(skill.split()))
    if not found:
        problems.append("SKILL.md states no version-places policy (`lives in exactly N places`)")
    else:
        token = found.group(1)
        stated_places = int(token) if token.isdigit() else NUMBER_WORDS.get(token.lower())
        if stated_places != expected_places:
            problems.append(f"SKILL.md says the version lives in {token!r} places, "
                            f"but {expected_places} carry it (frontmatter + {len(templates)} templates)")
    # The only allowed literals are frontmatter and each template's one `protocol:` line.
    # Template bodies are scanned too: exempting the whole file lets a second explanatory
    # literal drift on the next bump.
    scanned = pack_files(root)
    readme = root / "README.md"
    if readme.is_file():
        scanned.append(readme)
    front = re.match(r"^---\n(.*?)\n---\n", skill, re.S)
    skill_body = skill[front.end():] if front else skill
    literal = version_literal_pattern(want)
    for path in scanned:
        body = skill_body if path == root / "SKILL.md" else path.read_text(encoding="utf-8")
        if path.parent == root / "templates":
            body = "\n".join(line for line in body.splitlines()
                             if not line.lower().startswith("protocol:"))
        if literal.search(body):
            problems.append(f"{path.relative_to(root)} restates a protocol version literal; "
                            "refer to the handoff's `protocol:` line instead")
    return problems


def c2_referenced_files(root: Path) -> list[str]:
    problems: list[str] = []
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    named = set(re.findall(r"(?:references|templates)/[A-Za-z0-9._\-]+\.md", text))
    if not named:
        problems.append("SKILL.md names no pack file (references/… or templates/…)")
    problems.extend(f"SKILL.md names {rel} but it does not exist" for rel in sorted(named)
                    if not (root / rel).is_file())
    if not (root / "LICENSE").is_file():
        problems.append("required LICENSE is missing")
    return problems


def c3_host_independent(root: Path) -> list[str]:
    problems: list[str] = []
    public_files = pack_files(root) + [root / "README.md", root / "LICENSE"]
    for path in public_files:
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8")
        # The frontmatter is metadata (author/license); the protocol body is what travels.
        front = re.match(r"^---\n(.*?)\n---\n", body, re.S)
        body_only = body[front.end():] if front else body
        line_offset = body[:front.end()].count("\n") if front else 0
        for label, pattern in HOST_PATH_PATTERNS:
            for match in pattern.finditer(body_only):
                owner = match.groupdict().get("owner")
                if owner and PLACEHOLDER_SEGMENT.fullmatch(owner):
                    continue
                line = line_offset + body_only.count("\n", 0, match.start()) + 1
                problems.append(
                    f"{path.relative_to(root)}:{line} contains {label}: {match.group(0)!r}"
                )
    return problems


def phase1b_items(text: str) -> dict[int, str]:
    """Numbered items under `## Phase 1b`, up to the next `## ` heading."""
    m = re.search(r"^## Phase 1b.*?$", text, re.M)
    if not m:
        return {}
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.M)
    body = rest[: nxt.start()] if nxt else rest
    items: dict[int, list[str]] = {}
    current = None
    for line in body.splitlines():
        head = re.match(r"^(\d+)\.\s+", line)
        if head:
            current = int(head.group(1))
            items[current] = [line]
        elif current is not None:
            items[current].append(line)
    return {k: " ".join(v).strip() for k, v in items.items()}


def c4_phase1b_items(root: Path) -> list[str]:
    core = (root / "references/review-core.md")
    if not core.is_file():
        return ["references/review-core.md is missing"]
    items = phase1b_items(core.read_text(encoding="utf-8"))
    problems = []
    for n in range(1, REQUIRED_PHASE1B_ITEMS + 1):
        if n not in items:
            problems.append(f"Phase 1b item {n} is missing")
        elif len(items[n]) < 60:
            problems.append(f"Phase 1b item {n} is a stub ({len(items[n])} chars)")
    return problems


def c5_handoff_previous_report(root: Path) -> list[str]:
    """Both handoff templates name the previous report by absolute path."""
    problems: list[str] = []
    for name in PREVIOUS_REPORT_TEMPLATES:
        tpl = root / "templates" / name
        if not tpl.is_file():
            problems.append(f"templates/{name} is missing")
            continue
        body = tpl.read_text(encoding="utf-8")
        line = next((l for l in body.splitlines() if "previous report" in l.lower()), None)
        if line is None:
            problems.append(f"{tpl.name} has no `previous report` line")
        elif "/" not in line:
            problems.append(f"{tpl.name} `previous report` line carries no absolute path sample")
    return problems


def c6_previous_report_rule(root: Path) -> list[str]:
    problems: list[str] = []
    core = (root / "references/review-core.md").read_text(encoding="utf-8") if (root / "references/review-core.md").is_file() else ""
    low = core.lower()
    if "previous report" not in low:
        problems.append("review-core.md never says what a `previous report` is")
    if "absolute" not in low:
        problems.append("review-core.md does not require an absolute path for the previous report")
    shape = re.search(r"^## Return shape.*$", core, re.M)
    if not shape:
        problems.append("review-core.md has no `## Return shape` section")
    else:
        rest = core[shape.end():]
        missing = [f for f in RETURN_SHAPE_FIELDS if f not in rest]
        if missing:
            problems.append(f"`## Return shape` does not name {', '.join(missing)}")
    skill = (root / "SKILL.md").read_text(encoding="utf-8").lower()
    if "previous report" not in skill:
        problems.append("SKILL.md's procedure never mentions the previous report")
    return problems


def c7_call_order_and_self_reference(root: Path) -> list[str]:
    """The two checks 0.3.1 adds: a call-order trace and a self-reference/oracle check."""
    core = (root / "references/review-core.md")
    if not core.is_file():
        return ["references/review-core.md is missing"]
    text = core.read_text(encoding="utf-8")
    problems = []
    item10 = phase1b_items(text).get(10, "").lower()
    if not any(a in item10 for a in ("call order", "calls first", "short-circuit", "short circuit",
                                     "order of calls", "returns before", "who calls")):
        problems.append("Phase 1b item 10 does not name the call-order / short-circuit mechanism")
    low = text.lower()
    if not any(a in low for a in ("oracle", "self-referential", "self referential",
                                  "its own output", "the string it judges")):
        problems.append("review-core never states the self-reference / oracle check")
    return problems


def c8_item_numbering(root: Path) -> list[str]:
    """A change that adds an item must reach every file that names the item list.

    Two decisions this check encodes: item 9's two questions carry the literal labels 9a/9b
    (so "9b applies without a previous report" has a referent), and the false-positive guide --
    loaded on every review -- names the new highest item.
    """
    problems: list[str] = []
    core_path = root / "references/review-core.md"
    if not core_path.is_file():
        return ["references/review-core.md is missing"]
    item9 = phase1b_items(core_path.read_text(encoding="utf-8")).get(9, "").lower()
    for label in ("9a", "9b"):
        if label not in item9:
            problems.append(f"Phase 1b item 9 carries no literal `{label}` label")
    guide = root / "references/false-positive-guide.md"
    if not guide.is_file():
        problems.append("references/false-positive-guide.md is missing")
    elif "item 12" not in guide.read_text(encoding="utf-8").lower():
        problems.append("false-positive-guide.md does not name item 12 (the numbering change "
                        "did not reach every file that names the item list)")
    return problems


def c9_scoped_state(root: Path) -> list[str]:
    """Item 11: a reset or idempotency key is checked for scope and consumption, not by a pass rate.

    The three questions the item must ask -- which unit owns the state, whether the second
    use in that unit is suppressed, and which input makes the two uses differ -- are the
    mechanism; "idempotency" alone could mean any of them. A pass rate over rounds is
    explicitly not evidence: the run's input is not in the tree (FP-guide item 5).
    """
    core = root / "references/review-core.md"
    if not core.is_file():
        return ["references/review-core.md is missing"]
    item11 = phase1b_items(core.read_text(encoding="utf-8")).get(11, "").lower()
    if not item11:
        return ["Phase 1b item 11 (scoped/consumed reset state) is missing"]
    problems = []
    for label, alternatives in (
        ("scope (which unit owns the state)", ("scope", "lifetime", "owned by")),
        ("consumption (is the second use suppressed)", ("consum", "suppress", "second use")),
        ("idempotency keys", ("idempotency", "dedupe")),
        ("the evidence required (not a pass rate alone)", ("evidence", "independent")),
    ):
        if not any(a in item11 for a in alternatives):
            problems.append(f"Phase 1b item 11 does not name {label}")
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    if f"items 1–{REQUIRED_PHASE1B_ITEMS}" not in skill:
        problems.append("SKILL.md's verification line still stops at a lower item number")
    guide = root / "references/false-positive-guide.md"
    if not guide.is_file():
        problems.append("references/false-positive-guide.md is missing")
    elif "item 11" not in guide.read_text(encoding="utf-8").lower():
        problems.append("false-positive-guide.md does not name item 11")
    return problems


ITEM12_READ_MATERIAL = ("reads", "read as", "material", "input comes from")
ITEM12_JUDGES = ("judge", "subject it judges", "decides on")
ITEM12_SAME = ("same subject", "its own subject", "same artifact", "judge and judged",
               "own text", "self-reference")


def c10_judge_and_subject(root: Path) -> list[str]:
    """Item 12: a check that decides on the text of the thing it decides must be stated as a mechanism.

    The defect is not "a lint" and not "prose": it is that the material is read from the
    subject (the task statement or acceptance line) while the judgment is about that same
    subject. The two sides must be named separately, or the item would be a restatement of
    9b (a test oracle) and a reviewer reading item 12 would have no question to ask of a
    production check. The item must also be reachable without a previous report and
    without a diff (it is not `N/A` in full-tree mode).
    """
    core = root / "references/review-core.md"
    if not core.is_file():
        return ["references/review-core.md is missing"]
    text = core.read_text(encoding="utf-8")
    item12 = phase1b_items(text).get(12, "")
    if not item12:
        return ["Phase 1b item 12 (a judge reading its own subject) is missing"]
    low = item12.lower()
    problems = []
    for label, alternatives in (
        ("the material the check reads", ITEM12_READ_MATERIAL),
        ("what the check judges", ITEM12_JUDGES),
        ("that material and subject are the same artifact", ITEM12_SAME),
        ("an acceptance/statement field read as material", ("acceptance", "statement", "prose")),
        ("the item applies without a previous report", ("previous report", "without one")),
    ):
        if not any(a in low for a in alternatives):
            problems.append(f"Phase 1b item 12 does not name {label}")
    if "oracle" in low and "9b" not in low:
        problems.append("Phase 1b item 12 names an oracle without saying how it differs from 9b")
    if not any(a in low for a in ("full-tree", "with or without a diff", "without a diff")):
        problems.append("Phase 1b item 12 does not say it applies without a diff (full-tree mode)")
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    if f"items 1–{REQUIRED_PHASE1B_ITEMS}" not in skill:
        problems.append("SKILL.md's verification line still stops at a lower item number")
    # Only the review template walks the items; the property template carries no item list.
    review_tpl = root / "templates/handoff-review.md"
    for tpl in ([review_tpl] if review_tpl.is_file() else []):
        if "Item 12" not in tpl.read_text(encoding="utf-8"):
            problems.append(f"{tpl.name} does not carry the item 12 instruction line")
    guide = root / "references/false-positive-guide.md"
    if not guide.is_file():
        problems.append("references/false-positive-guide.md is missing")
    elif "item 12" not in guide.read_text(encoding="utf-8").lower():
        problems.append("false-positive-guide.md does not name item 12 (a concern about a judge "
                        "reading its own subject is not dropped for passing)")
    pre = text.split("## Modes", 1)[0].lower()
    if "item 12" not in pre:
        problems.append("Preconditions never say item 12 still applies without a previous report")
    return problems


def _copy_pack(src: Path, dst: Path) -> None:
    for rel in ("SKILL.md", "README.md", "references", "templates"):
        s = src / rel
        if s.is_file():
            shutil.copy2(s, dst / rel)
        elif s.is_dir():
            shutil.copytree(s, dst / rel)


def _rewrite_item(root: Path, n: int, fn) -> bool:
    """Replace Phase 1b item n in a copy of the pack with fn(item text); False if it is absent."""
    core = root / "references/review-core.md"
    text = core.read_text(encoding="utf-8")
    m = re.search(r"^## Phase 1b.*?$", text, re.M)
    if not m:
        return False
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.M)
    end = m.end() + (nxt.start() if nxt else len(rest))
    block = text[m.end():end]
    item = re.search(rf"^{n}\.[ \t]+.*(?:\n(?!\d+\.[ \t]|## ).*)*", block, re.M)
    if not item:
        return False
    core.write_text(text[:m.end()] + block[:item.start()] + fn(item.group(0))
                    + block[item.end():] + text[end:], encoding="utf-8")
    return True


def c11_regression_cases(root: Path) -> list[str]:
    """E1/E2: pin what 0.3.3 added, so a later edit that drops the mechanism fails here.

    Each case mutates a throwaway copy of the pack and requires the check under test to name
    the defect, with the same STAGE id and message text the real gate would print. The copy
    means this gate never reads the run directory and never writes to the pack.
    E1 (item 11): the scope / consumption / evidence questions are what C9 must ask. The case
    rewrites them into equal-length filler, so a check that only counted characters, or only
    looked for "idempotency", would let a rewritten item through.
    E2 (item 12): an item removed from the copy must be reported by the item-count gate and
    by the judge reader gate alike.
    """
    problems: list[str] = []
    if c9_scoped_state(root):
        problems.append("C9 fails the unmodified pack; E1 cannot be pinned against it")
    if c10_judge_and_subject(root):
        problems.append("C10 fails the unmodified pack; E2 cannot be pinned against it")
    if problems:
        return problems

    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp)
        _copy_pack(root, dst)

        def blank(block: str) -> str:
            # Strip every alternative C9 accepts for the three questions -- the words of the
            # item's own title ("Scoped, consumed state ...") included, since a check that only
            # reads the title would otherwise pass a body with no question left in it.
            return re.sub(r"(?i)(scope[l]?|lifetime|owned|consum\w*|suppress\w*|second|use|"
                          r"evidence|independent)",
                          lambda m: "z" * len(m.group(0)), block)

        if not _rewrite_item(dst, 11, blank):
            problems.append("E1: item 11 is absent from the copy, so the case cannot be built")
        else:
            got = c9_scoped_state(dst)
            for label in ("scope (which unit owns the state)",
                          "consumption (is the second use suppressed)",
                          "the evidence required (not a pass rate alone)"):
                want = f"Phase 1b item 11 does not name {label}"
                if want not in got:
                    problems.append(f"E1: item 11 reworded without its "
                                    f"'{label.split(' (')[0]}' question is no longer caught by C9")

    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp)
        _copy_pack(root, dst)
        if not _rewrite_item(dst, 12, lambda _block: ""):
            problems.append("E2: item 12 is absent from the copy, so the case cannot be built")
        else:
            for cid, fn in (("C4", c4_phase1b_items), ("C10", c10_judge_and_subject)):
                got = fn(dst)
                if not any("item 12" in g for g in got):
                    problems.append(f"E2: a pack without item 12 is no longer caught by {cid}")
    return problems


class _Req:
    """Collects `where does not state what` problems; every phrase is matched flattened and case-folded."""

    def __init__(self, problems: list[str]):
        self.problems = problems

    def all(self, where: str, text: str, label: str, phrases) -> None:
        flat = _flat(text).lower()
        missing = [p for p in phrases if _flat(p).lower() not in flat]
        if missing:
            self.problems.append(f"{where} does not state {label} (missing: {'; '.join(missing)})")


def _next_heading_start(text: str, max_level: int) -> int:
    """Offset of the next Markdown heading at level 2..max_level, ignoring fenced code."""
    offset = 0
    in_fence = False
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        elif not in_fence:
            match = re.match(r"^(#{2,}) ", line)
            if match and len(match.group(1)) <= max_level:
                return offset
        offset += len(line)
    return len(text)


def _section(text: str, heading: str) -> str:
    """Body of `## heading` up to the next unfenced `## ` heading ('' when absent)."""
    m = re.search(rf"^## {re.escape(heading)}.*$", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    return rest[:_next_heading_start(rest, 2)]


def _subsection(text: str, heading: str) -> str:
    """Body of `### heading` up to the next unfenced `##`/`###` heading."""
    m = re.search(rf"^### {re.escape(heading)}.*$", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    return rest[:_next_heading_start(rest, 3)]


def _flat(text: str) -> str:
    return " ".join(text.split())


def skill_description(text: str) -> str | None:
    front = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    found = re.search(r"^description:\s*(.*?)\s*$", front.group(1), re.M) if front else None
    if not found:
        return None
    value = found.group(1)
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'" else value


def c12_two_procedures(root: Path) -> list[str]:
    """The pack ships two procedures. The removed one must be gone from every surface.

    A pack that still lists a third procedure, a third template, or a file that only that
    procedure loaded is not the pack the version claims. The description length rule rides
    here because the description is the surface that names the procedure set.
    """
    problems: list[str] = []
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    for name in PROCEDURES:
        if not re.search(rf"^### {name}\s*$", skill, re.M):
            problems.append(f"SKILL.md has no `### {name}` procedure")
    procedure_body = _section(skill, "Procedure")
    procedure_headings = re.findall(r"^###\s+(.+?)\s*$", procedure_body, re.M)
    if procedure_headings != list(PROCEDURES):
        problems.append(f"SKILL.md `## Procedure` has {procedure_headings}, expected exactly "
                        f"{list(PROCEDURES)}")
    if re.search(r"^### Comprehension\s*$", skill, re.M):
        problems.append("SKILL.md still carries a `### Comprehension` procedure")
    if "three sibling" in skill.lower():
        problems.append("SKILL.md still calls the procedures `three sibling`")
    low = skill.lower()
    if "comprehension" in low:
        problems.append("SKILL.md still mentions comprehension")
    tdir = root / "templates"
    got = sorted(p.name for p in tdir.glob("*.md")) if tdir.is_dir() else []
    if got != sorted(REQUIRED_TEMPLATES):
        problems.append(f"templates/ holds {got}, expected exactly {sorted(REQUIRED_TEMPLATES)}")
    for rel in REMOVED_PATHS:
        if (root / rel).exists():
            problems.append(f"{rel} still exists; the removed procedure's artifacts must be gone")
    for path in pack_files(root):
        if "comprehension" in path.read_text(encoding="utf-8").lower():
            problems.append(f"{path.relative_to(root)} still mentions comprehension")
    readme = root / "README.md"
    if not readme.is_file():
        problems.append("README.md is missing")
    else:
        rm = readme.read_text(encoding="utf-8")
        if "comprehension" in rm.lower():
            problems.append("README.md still mentions comprehension")
        if "two sibling procedures" not in _flat(rm).lower():
            problems.append("README.md does not describe two sibling procedures")
    desc = skill_description(skill)
    if desc is None:
        problems.append("SKILL.md frontmatter has no `description:` line")
        return problems
    if len(desc) > MAX_DESCRIPTION:
        problems.append(f"SKILL.md description is {len(desc)} characters, over the {MAX_DESCRIPTION} limit")
    if not desc.endswith("."):
        problems.append("SKILL.md description does not end in a period")
    for word in ("review", "property"):
        if word not in desc.lower():
            problems.append(f"SKILL.md description does not mention {word}")
    return problems


def c13_lean_mode(root: Path) -> list[str]:
    """The exhaustive lane is part of the property procedure, not a separate procedure.

    Formalized means a reader can decide from the pack alone: when the lane applies, when to
    skip it, which files it needs, and what its return must carry. The acceptance items are
    the ones a sampled return does not have -- the theorem table, the production firing
    condition, and the fix proved against the legitimate cases.
    """
    proto = root / "references/property.md"
    if not proto.is_file():
        return ["references/property.md is missing"]
    pt = proto.read_text(encoding="utf-8")
    problems: list[str] = []
    req = _Req(problems)
    preconditions = _section(pt, "Preconditions")
    if not preconditions.strip():
        problems.append("references/property.md has no `## Preconditions` section")
    else:
        req.all("references/property.md `## Preconditions`", preconditions,
                "lane-specific dependencies rather than a sampled-only global prerequisite",
                ("Sampled lane", "property library", "Exhaustive-only lane", "Lean toolchain",
                 "does not require the repository runtime or a property library"))
    lane = _section(pt, "Lane selection")
    if not lane.strip():
        problems.append("references/property.md has no `## Lane selection` section")
    else:
        req.all("references/property.md `## Lane selection`", lane,
                "the finite-map test that makes the exhaustive lane available and the sampled default",
                ("finite-map test", "classification", "exhaustive lane", "sampled lane is the default"))
        req.all("references/property.md `## Lane selection`", lane,
                "the skip test (no implementation, trivially true, design judgement)",
                ("no finite executable map", "no implementation", "trivially true",
                 "design judgement"))
        req.all("references/property.md `## Lane selection`", lane,
                "the handoff's sampled, exhaustive and auto lane-token semantics",
                ("`LANE=sampled`", "`LANE=exhaustive`", "`LANE=auto`"))
    environment = _subsection(pt, "0. Environment")
    if not environment.strip():
        problems.append("references/property.md has no `### 0. Environment` subsection")
    else:
        req.all("references/property.md `### 0. Environment`", environment,
                "lane-specific setup without a property-library requirement for exhaustive-only work",
                ("For `LANE=sampled`", "For `LANE=exhaustive`", "Lean toolchain",
                 "does not require a property library or repository runtime"))
    procedure = _section(pt, "Procedure")
    req.all("references/property.md `## Procedure`", procedure,
            "that exhaustive-only work skips the sampled-test steps",
            ("sampled lane continues through steps 3–4",
             "exhaustive lane skips those sampled-only steps"))
    mode = _section(pt, "Exhaustive mode (Lean)")
    if not mode.strip():
        return problems + ["references/property.md has no `## Exhaustive mode (Lean)` section"]
    req.all("references/property.md `## Exhaustive mode (Lean)`", mode,
            "that the lane closes properties with `by decide` over a finite map",
            ("finite map", "by decide", "no counterexample exists"))
    req.all("references/property.md `## Exhaustive mode (Lean)`", mode,
            "the two files the mode requires",
            ("references/lean.md", "references/lean-handoff-example.md"))
    req.all("references/property.md `## Exhaustive mode (Lean)`", mode,
            "that the model lives outside the repository and the target stays read-only",
            ("outside the target repository", "read-only"))
    req.all("references/property.md `## Exhaustive mode (Lean)`", mode,
            "the property / result / theorem table as the return's first item",
            ("property / result / theorem table", "theorem name"))
    req.all("references/property.md `## Exhaustive mode (Lean)`", mode,
            "each counterexample with the production condition under which it fires",
            ("production condition under which it fires",))
    req.all("references/property.md `## Exhaustive mode (Lean)`", mode,
            "the fix predicate proved to remove the counterexample and keep the legitimate cases passing",
            ("fix predicate", "legitimate cases still pass", "disabling the behaviour is not a fix"))
    req.all("references/property.md `## Exhaustive mode (Lean)`", mode,
            "the limits and the artifact path",
            ("the limits", "`lake build`", "absolute path"))
    req.all("references/property.md `## Exhaustive mode (Lean)`", mode,
            "the skip outcome and its reason",
            ("say `SKIPPED` and give the reason", "trivially true",
             "skipped exhaustive-only pass uses the skipped return schema",
             "requires no theorem table, `.lean` artifact, or build result"))
    sampled = _subsection(pt, "Sampled-mode return")
    if not sampled.strip():
        problems.append("references/property.md has no `### Sampled-mode return` subsection")
    else:
        req.all("references/property.md `### Sampled-mode return`", sampled,
                "the sampled header, findings, no-counterexample, carried and notes schema",
                ("lane=sampled", "seeds <list>", "examples <n/...>", "`## Findings`",
                 "`## No-counterexample summary`", "`## Carried / unverified`", "`## Notes`"))
        req.all("references/property.md `### Sampled-mode return`", sampled,
                "the sampling-not-assurance disclaimer", (SAMPLED_DISCLAIMER,))
        if "| lane=sampled |" not in sampled:
            problems.append("references/property.md `### Sampled-mode return` has no exact "
                            "`| lane=sampled |` header field")
    ret = _subsection(pt, "Exhaustive-mode return")
    if not ret.strip():
        problems.append("references/property.md has no `### Exhaustive-mode return` subsection")
    else:
        req.all("references/property.md `### Exhaustive-mode return`", ret,
                "the table header and the firing condition section",
                ("| property | result | theorem |", "## Counterexample",
                 "production condition under which it fires"))
        req.all("references/property.md `### Exhaustive-mode return`", ret,
                "the fix pair and the limits sections",
                ("## Fix predicate", "legitimate cases", "## Limits"))
        req.all("references/property.md `### Exhaustive-mode return`", ret,
                "an exhaustive-only header without sampled fields and a proof-scoped claim",
                ("exhaustive-only", "lane=exhaustive", "does not carry meaningless `seeds` or",
                 "does not verify the source system"))
        req.all("references/property.md `### Exhaustive-mode return`", ret,
                "that the sampling disclaimer applies only when sampling ran",
                ("when sampling also ran", "Do not append the sampling disclaimer to an exhaustive-only return"))
    skipped = _subsection(pt, "Skipped exhaustive return")
    if not skipped.strip():
        problems.append("references/property.md has no `### Skipped exhaustive return` subsection")
    else:
        req.all("references/property.md `### Skipped exhaustive return`", skipped,
                "a caller-parseable skip-only schema and its evidence",
                ("status=SKIPPED", "## Skipped", "reason: <no finite executable map",
                 "evidence: <file/range inspected>", "## Notes"))
        req.all("references/property.md `### Skipped exhaustive return`", skipped,
                "the skipped-lane waiver and combined-lane routing",
                ("Do not emit a property / result / theorem table", "lane did not execute",
                 "Do not append the sampling disclaimer", "If sampling also ran"))
        for exact, label in (("| status=SKIPPED", "case-sensitive status field"),
                             ("\n## Skipped\n", "Skipped section in the schema block"),
                             ("\n## Notes\n", "Notes section in the schema block")):
            if exact not in skipped:
                problems.append("references/property.md `### Skipped exhaustive return` "
                                f"does not state the exact {label}")
    tpl = root / "templates" / PROPERTY_TEMPLATE
    if not tpl.is_file():
        problems.append(f"templates/{PROPERTY_TEMPLATE} is missing")
    else:
        template_text = tpl.read_text(encoding="utf-8")
        inputs = _section(template_text, "Inputs")
        req.all(f"templates/{PROPERTY_TEMPLATE} `## Inputs`", inputs,
                "the sampled, exhaustive and auto lane tokens plus auto semantics",
                ("<sampled | exhaustive | auto>", "`auto` lets the worker apply the finite-map test"))
        output = _section(template_text, "Output")
        req.all(f"templates/{PROPERTY_TEMPLATE} `## Output`", output,
                "separate sampled, exhaustive-only, skipped and combined output rules",
                ("Sampled lane", "sampling-not-assurance line", "Exhaustive-only lane",
                 "Skipped exhaustive-only lane", "status=SKIPPED", "Both lanes",
                 "Both lanes — include both schemas", "Do not append the sampling disclaimer",
                 "transcribed bounded domain"))
    skill_property = _subsection((root / "SKILL.md").read_text(encoding="utf-8"), "Property")
    req.all("SKILL.md `### Property`", skill_property,
            "the default sampled return and the skipped exhaustive return",
            ("**sampled** (default)", "sampled mode carries findings", "no-counterexample summary",
             "sampling-not-assurance line", "status=SKIPPED", "requires no theorem table"))
    readme = (root / "README.md").read_text(encoding="utf-8")
    req.all("README.md", readme, "the sampled default and skipped exhaustive return",
            ("property pass defaults to a sampled lane", "**sampled** (default)",
             "status=SKIPPED", "needs no theorem table"))
    return problems


def c14_lean_files(root: Path) -> list[str]:
    """The lane's own two files must be usable: the protocol closed, the shape runnable."""
    problems: list[str] = []
    proto = root / LEAN_PROTOCOL
    example = root / LEAN_EXAMPLE
    if not proto.is_file():
        return [f"{LEAN_PROTOCOL} is missing"]
    if not example.is_file():
        return [f"{LEAN_EXAMPLE} is missing"]
    pt = proto.read_text(encoding="utf-8")
    req = _Req(problems)
    for heading, label, phrases in (
        ("When to use it", "the finite-map shapes that select the lane",
         ("finite map", "setting or permission table", "identification or resolution function",
          "state machine", "normalization or equivalence", "classification")),
        ("When to skip it", "the skip conditions and that skipping is recorded, not failed",
         ("no finite executable map", "no implementation", "trivially true",
          "with the reason why formalization has no value", "Skipping is not a failure")),
        ("Procedure", "the transcription steps, the decide close and the fix pair",
         ("language-native parser or AST", "smallest compilable slice", "file:line",
          "applies equally to Python, JS/TS, Rust, Go", "by decide", "minimal counterexample",
          "legitimate cases still pass")),
        ("Environment", "the Lean 4 core environment",
         ("elan toolchain install", "lake build", "explicit list")),
        ("Pitfalls", "the measured pitfalls of the lane",
         ("set_option maxRecDepth", "fully qualified")),
        ("Acceptance", "the executed-lane acceptance items and skipped-lane waiver",
         ("property / result / theorem", "production condition", "legitimate cases still pass",
          "limits", "absolute path", "When the skip test fires", "not required because the lane did not run")),
        ("Skipped return", "the skip-only schema, evidence and artifact waiver",
         ("status=SKIPPED", "`## Skipped`", "exact reason", "file/range evidence",
          "`## Notes`", "Do not emit theorem results or a Lean artifact")),
    ):
        body = _section(pt, heading)
        if not body.strip():
            problems.append(f"{LEAN_PROTOCOL} has no `## {heading}` section")
        else:
            req.all(f"{LEAN_PROTOCOL} `## {heading}`", body, label, phrases)
    req.all(f"{LEAN_PROTOCOL} intro", pt.split("\n## ", 1)[0],
            "that the lane proves absence over a bounded domain, not a sample",
            ("finite map", "by decide", "no counterexample exists"))
    ex = example.read_text(encoding="utf-8")
    req.all(f"{LEAN_EXAMPLE}", ex,
            "the handoff fields, the return table, the firing condition, the fix pair, the limits and the artifact path",
            ("<run_id>", "<BASE>...<HEAD>", "<REPO_ABS>", "Previous report",
             "| property | result | theorem |", "production condition under which it fires",
             "legitimate cases still pass", "**Limits**", "absolute `.lean` path", "`lake build`"))
    req.all(f"{LEAN_EXAMPLE}", ex,
            "conditional artifact destinations and the complete skip-only return",
            ("<THROWAWAY_ABS>", "only when `RUN_ABS` was supplied", "otherwise return it on stdout",
             "status=SKIPPED", "## Skipped", "No `.lean` artifact or `lake build` result is required"))
    req.all(f"{LEAN_EXAMPLE}", ex, "that the target repository is read-only for this hop",
            ("Read-only on the target repository", "`file:line`", "not checked"))
    req.all(f"{LEAN_EXAMPLE}", ex, "the skip path", ("SKIPPED", "the reason"))
    return problems


def c15_firing_condition(root: Path) -> list[str]:
    """The firing rule must hold in every file that states it, not in the lane protocol alone.

    A reviewer who reads only `SKILL.md`, only `property.md`, or only `lean.md` must not come
    away with a lower bar: a counterexample is a finding only when it can fire in production,
    and uniqueness is not identity.
    """
    problems: list[str] = []
    for rel in ("SKILL.md", "references/property.md", LEAN_PROTOCOL):
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel} is missing")
            continue
        pitfalls = _section(path.read_text(encoding="utf-8"), "Pitfalls")
        if not pitfalls.strip():
            problems.append(f"{rel} has no `## Pitfalls` section")
            continue
        low = _flat(pitfalls).lower()
        if FIRING_RULE.lower() not in low:
            problems.append(f"{rel} `## Pitfalls` does not state that a {FIRING_RULE}")
        if "firing condition" not in low:
            problems.append(f"{rel} `## Pitfalls` does not say to state the firing condition")
    for rel in ("SKILL.md", "references/property.md", LEAN_PROTOCOL):
        path = root / rel
        if not path.is_file():
            continue
        pitfalls = _section(path.read_text(encoding="utf-8"), "Pitfalls")
        low = _flat(pitfalls).lower()
        if IDENTITY_RULE.lower() not in low:
            problems.append(f"{rel} `## Pitfalls` does not state that uniqueness is not identity")
        missing_actions = [phrase for phrase in IDENTITY_ACTIONS if phrase not in low]
        if missing_actions:
            problems.append(f"{rel} `## Pitfalls` does not state the identity gate's coverage "
                            f"and limits (missing: {', '.join(missing_actions)})")
    for rel in PROOF_SCOPE_FILES:
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel} is missing")
            continue
        text = _flat(path.read_text(encoding="utf-8")).lower()
        if PROOF_SCOPE_RULE.lower() not in text:
            problems.append(f"{rel} does not state the proof-scope rule: {PROOF_SCOPE_RULE}")
    return problems


def c16_report_consumer(root: Path) -> list[str]:
    """A caller that parses a return has its own contract; the pack states it once."""
    doc = root / CONSUMER_DOC
    if not doc.is_file():
        return [f"{CONSUMER_DOC} is missing"]
    problems: list[str] = []
    text = _flat(doc.read_text(encoding="utf-8")).lower()
    for label, phrase in CONSUMER_RULES:
        if _flat(phrase).lower() not in text:
            problems.append(f"{CONSUMER_DOC} does not state {label}")
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    if CONSUMER_DOC not in skill:
        problems.append(f"SKILL.md does not name {CONSUMER_DOC}")
    readme = root / "README.md"
    if readme.is_file() and CONSUMER_DOC not in readme.read_text(encoding="utf-8"):
        problems.append(f"README.md does not list {CONSUMER_DOC}")
    return problems


def c17_readme_invocations(root: Path) -> list[str]:
    """The README's commands are the contract: they must be the ones that run.

    A reader who copies the block must reach the gate and the tests. So the two commands are
    pinned, every test path the README names must exist, and the discover pattern must match
    the test files actually present.
    """
    readme = root / "README.md"
    if not readme.is_file():
        return ["README.md is missing"]
    problems: list[str] = []
    rm = readme.read_text(encoding="utf-8")
    flat = _flat(rm)
    if GATE_COMMAND not in flat:
        problems.append(f"README.md does not give the gate invocation `{GATE_COMMAND}`")
    if TEST_COMMAND not in flat:
        problems.append(f"README.md does not give the test invocation `{TEST_COMMAND}`")
    if "PACK_OK" not in flat:
        problems.append("README.md does not say the gate prints PACK_OK on success")
    if TEST_FILE not in rm:
        problems.append(f"README.md does not list {TEST_FILE}")
    if "status=SKIPPED" not in rm:
        problems.append("README.md does not state the skipped exhaustive return status")
    if not (root / TEST_FILE).is_file():
        problems.append(f"{TEST_FILE} is missing")
    named = set(re.findall(r"tests/[A-Za-z0-9._\-/]+\.py", rm))
    for rel in sorted(named):
        if not (root / rel).is_file():
            problems.append(f"README.md names {rel} but it does not exist")
    discovered = {f"tests/{p.name}" for p in (root / "tests").glob("test_*.py")}
    if not discovered:
        problems.append("tests/ holds no `test_*.py` file for the discover pattern")
    for rel in sorted(discovered - {TEST_FILE}):
        if rel not in rm:
            problems.append(f"{rel} is not listed in README.md")
    if not re.search(r"both\**\s+templates", flat, re.I):
        problems.append("README.md does not say the version bump reaches both templates")
    return problems


def c18_regression_cases(root: Path) -> list[str]:
    """E3: pin the 0.5.0 procedure mechanisms by mutating copies and naming each defect.

    Each case removes exactly one mechanism from a copy and requires the check that owns it
    to name that mechanism. A check that only looked for a word elsewhere in the file, or
    only for the file's presence, would let the mutation through and fail here.
    """
    problems: list[str] = []
    owners = {"C12": c12_two_procedures, "C13": c13_lean_mode, "C14": c14_lean_files,
              "C15": c15_firing_condition, "C16": c16_report_consumer,
              "C17": c17_readme_invocations}
    for cid, fn in owners.items():
        if fn(root):
            problems.append(f"{cid} fails the unmodified pack; E3 cannot be pinned against it")
    if problems:
        return problems

    def case(mutate, cid: str, fragment: str, rel: str, what: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp)
            _copy_pack(root, dst)
            target = dst / rel
            before = target.read_text(encoding="utf-8")
            after = mutate(before)
            if after == before:
                problems.append(f"E3: {what} could not be mutated in {rel}")
                return
            target.write_text(after, encoding="utf-8")
            got = owners[cid](dst)
        if not any(fragment in g for g in got):
            problems.append(f"E3: {what} is no longer caught by {cid} "
                            f"(expected a message containing {fragment!r})")

    case(lambda t: t.replace("## Exhaustive mode (Lean)", "## Extra lane"),
         "C13", "has no `## Exhaustive mode (Lean)` section", "references/property.md",
         "the exhaustive mode heading")
    case(lambda t: re.sub(r"production condition under which it fires", "condition", t),
         "C13", "production condition under which it fires", "references/property.md",
         "the production firing condition in the mode section")
    case(lambda t: re.sub(r"legitimate cases still pass", "counterexample is gone", t),
         "C13", "legitimate cases", "references/property.md",
         "the legitimate-cases half of the fix pair")
    case(lambda t: t.replace("### Sampled-mode return", "### Sampling notes"),
         "C13", "has no `### Sampled-mode return` subsection", "references/property.md",
         "the sampled return schema")
    case(lambda t: t.replace(SAMPLED_DISCLAIMER, "Sampling passed.", 1),
         "C13", "sampling-not-assurance disclaimer", "references/property.md",
         "the sampled return disclaimer")
    case(lambda t: t.replace("### Skipped exhaustive return", "### Skip notes"),
         "C13", "has no `### Skipped exhaustive return` subsection", "references/property.md",
         "the skip-only return schema")
    case(lambda t: re.sub(r"The sampled-lane mandatory line applies when sampling also ran\..*?"
                          r"exhaustive-only return\.", "The same line always applies.", t,
                          count=1, flags=re.S),
         "C13", "sampling disclaimer applies only when sampling ran", "references/property.md",
         "the exhaustive-only disclaimer scope")
    case(lambda t: t.replace('"Uniqueness holds" is not "identity holds"',
                             '"Uniqueness holds" is not "coverage holds"', 1),
         "C15", "uniqueness is not identity", "SKILL.md",
         "the uniqueness-versus-identity rule in the skill entry point")
    case(lambda t: t.replace("- **A counterexample that cannot fire in production is not a finding.**",
                             "- A counterexample is a finding."),
         "C15", "cannot fire in production", "references/lean.md",
         "the firing rule in the lane protocol")
    case(lambda t: re.sub(r"## Acceptance", "## Done", t),
         "C14", "has no `## Acceptance` section", "references/lean.md",
         "the acceptance section of the lane protocol")
    case(lambda t: t.replace("not required because the lane did not run",
                             "always required", 1),
         "C14", "skipped-lane waiver", "references/lean.md",
         "the skipped-lane artifact waiver")
    case(lambda t: t.replace("### Property", "### Extra\n\n### Property", 1),
         "C12", "expected exactly", "SKILL.md", "an arbitrary third procedure")
    case(lambda t: re.sub(r"\s+".join(re.escape(w) for w in PROOF_SCOPE_RULE.split()),
                          "The proof verifies everything.", t, count=1),
         "C15", "proof-scope rule", "README.md", "the public proof-scope rule")
    case(lambda t: t.replace(TEST_COMMAND, "python3 -m unittest"),
         "C17", "test invocation", "README.md", "the README test invocation")
    case(lambda t: re.sub(r"(?m)^- Match the consumer.*$", "", t),
         "C16", "the schema-first refusal", CONSUMER_DOC,
         "the schema-first consumer rule")

    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp)
        _copy_pack(root, dst)
        (dst / "references/comprehension.md").write_text("# Comprehension\n", encoding="utf-8")
        got = c12_two_procedures(dst)
        if not any("references/comprehension.md still exists" in g for g in got):
            problems.append("E3: a reintroduced comprehension protocol is no longer caught by C12")
    return problems


CHECKS = (
    ("C1", "version consistent in SKILL.md and every handoff template", c1_version_consistency),
    ("C2", "every pack file SKILL.md names exists", c2_referenced_files),
    ("C3", "public files carry no machine-local home path", c3_host_independent),
    ("C4", f"review-core Phase 1b has items 1-{REQUIRED_PHASE1B_ITEMS}, none a stub", c4_phase1b_items),
    ("C5", "each handoff template names the previous report by absolute path", c5_handoff_previous_report),
    ("C6", "previous-report rule + single return shape are stated", c6_previous_report_rule),
    ("C7", "call-order trace + self-reference/oracle check are stated", c7_call_order_and_self_reference),
    ("C8", "the item list reached every file (9a/9b labels, FP guide names item 12)", c8_item_numbering),
    ("C9", "reset/idempotency state is scoped, consumed and evidenced as item 11", c9_scoped_state),
    ("C10", "item 12 names the material a judge reads and the subject it judges as one", c10_judge_and_subject),
    ("C11", "E1/E2 regression: item 11's mechanism and item 12's presence are pinned", c11_regression_cases),
    ("C12", "two procedures only: the removed one is gone from every surface", c12_two_procedures),
    ("C13", "the sampled and Lean exhaustive lanes are formalized inside property", c13_lean_mode),
    ("C14", "the lane protocol and its worked handoff are complete", c14_lean_files),
    ("C15", "firing, identity and proof-scope rules hold across public surfaces", c15_firing_condition),
    ("C16", "report-consumer validation is stated and reachable", c16_report_consumer),
    ("C17", "the README's own commands and test paths exist", c17_readme_invocations),
    ("C18", "E3 regression: the 0.5.0 procedure mechanisms are pinned", c18_regression_cases),
)


def collect(root: Path) -> list[str]:
    """Every `STAGE: C<n> ...` line the gate would print for this pack (empty = pass)."""
    if not (root / "SKILL.md").is_file():
        return [f"STAGE: C0 no SKILL.md under {root}"]
    lines: list[str] = []
    for cid, what, fn in CHECKS:
        for p in fn(root):
            lines.append(f"STAGE: {cid} {what} -- {p}")
    return lines


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parent.parent
    lines = collect(root)
    for line in lines:
        print(line)
    if lines:
        return 1
    print(f"PACK_OK {root} ({skill_version((root / 'SKILL.md').read_text(encoding='utf-8'))})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
