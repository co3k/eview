#!/usr/bin/env python3
"""Contract and mutation tests for the eview pack.

What this is: prompt *contract* tests. They check that the protocols, the handoff templates
and the docs state the rules the accepted design requires, and that mutated throwaway copies
of the pack are rejected by the intended check (asserted by its `STAGE:` id and message, not
by exit status alone).

What this is not: an LLM efficacy benchmark. Nothing here runs a reviewer or a prover, grades
a report, or says how well any model reviews. A reader-level smoke is the caller's job.

Stdlib only, no network. Every scratch directory comes from `tempfile`, so it follows the
configured TMPDIR; no fixed shared path is used and the pack itself is never written.

Usage: python3 tests/test_pack.py    (or: python3 -m unittest discover -s tests -p 'test_*.py')
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

_spec = importlib.util.spec_from_file_location("accept_pack", HERE / "accept_pack.py")
assert _spec is not None and _spec.loader is not None
ap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ap)

SKILL = "SKILL.md"
README = "README.md"
LICENSE = "LICENSE"
PROPERTY = "references/property.md"
LEAN = "references/lean.md"
LEAN_EXAMPLE = "references/lean-handoff-example.md"
CONSUMER = "references/report-consumer-validation.md"
REVIEW_TPL = "templates/handoff-review.md"
PROPERTY_TPL = "templates/handoff-property.md"


# --------------------------------------------------------------------------- helpers

class PackCopy:
    """A throwaway copy of the pack under tempfile's directory, removed on exit."""

    def __enter__(self) -> "PackCopy":
        self._tmp = tempfile.TemporaryDirectory(prefix="eview-pack-")
        self.root = Path(self._tmp.name)
        for rel in (SKILL, README, LICENSE, "references", "templates", "tests"):
            src = ROOT / rel
            if src.is_file():
                shutil.copy2(src, self.root / rel)
            elif src.is_dir():
                if rel == "tests":
                    shutil.copytree(src, self.root / "tests",
                                    ignore=shutil.ignore_patterns("__pycache__"))
                else:
                    shutil.copytree(src, self.root / rel)
        return self

    def __exit__(self, *exc) -> None:
        self._tmp.cleanup()

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def write(self, rel: str, text: str) -> None:
        (self.root / rel).write_text(text, encoding="utf-8")

    def sub(self, rel: str, old: str, new: str, count: int = 1) -> None:
        """Replace `old` in a copy (count=0: every occurrence); fail loudly if it did not apply.

        Prose in the pack wraps at arbitrary columns, so `old` matches across any whitespace.
        """
        text = self.read(rel)
        pattern = re.compile(r"\s+".join(re.escape(w) for w in old.split()))
        if not pattern.search(text):
            raise AssertionError(f"mutation target not found in {rel}: {old!r}")
        self.write(rel, pattern.sub(lambda _m: new, text, count=count))

    def sub_in_section(self, rel: str, heading: str, old: str, new: str, level: str = "##") -> None:
        """Replace `old` once, only inside `<level> heading` (whitespace-flexible); fail if absent there."""
        text = self.read(rel)
        m = re.search(rf"^{re.escape(level)} {re.escape(heading)}.*$", text, re.M)
        if not m:
            raise AssertionError(f"no section {level} {heading} in {rel}")
        rest = text[m.end():]
        end = m.end() + ap._next_heading_start(rest, len(level))
        body = text[m.end():end]
        pattern = re.compile(r"\s+".join(re.escape(w) for w in old.split()))
        if not pattern.search(body):
            raise AssertionError(f"mutation target not found in {rel} {level} {heading}: {old!r}")
        self.write(rel, text[:m.end()] + pattern.sub(lambda _m: new, body, count=1) + text[end:])

    def drop_lines(self, rel: str, needle: str) -> int:
        lines = self.read(rel).splitlines(keepends=True)
        kept = [l for l in lines if needle.lower() not in l.lower()]
        if len(kept) == len(lines):
            raise AssertionError(f"no line containing {needle!r} in {rel}")
        self.write(rel, "".join(kept))
        return len(lines) - len(kept)

    def remove(self, rel: str) -> None:
        (self.root / rel).unlink()


def stage_ids(lines: list[str]) -> set[str]:
    return {m.group(1) for l in lines if (m := re.match(r"STAGE: (C\d+) ", l))}


def flat(text: str) -> str:
    return " ".join(text.split())


class GateAssertions(unittest.TestCase):
    def assertDiag(self, lines: list[str], cid: str, fragment: str) -> None:
        hits = [l for l in lines if l.startswith(f"STAGE: {cid} ") and fragment in l]
        self.assertTrue(hits, f"expected a `STAGE: {cid}` line containing {fragment!r}; got:\n"
                              + "\n".join(lines or ["(no failures)"]))

    def assertClean(self, lines: list[str]) -> None:
        self.assertEqual(lines, [], "the mutation was supposed to leave the pack acceptable")


# ------------------------------------------------------------------- the real pack

class RealPackTests(GateAssertions):
    def test_unmodified_pack_passes_every_check(self):
        self.assertEqual(ap.collect(ROOT), [])

    def test_cli_reports_ok_then_rejects_a_mutated_copy(self):
        ok = subprocess.run([sys.executable, str(HERE / "accept_pack.py"), str(ROOT)],
                            capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertTrue(ok.stdout.startswith("PACK_OK "), ok.stdout)
        with PackCopy() as pack:
            pack.remove(PROPERTY)
            bad = subprocess.run([sys.executable, str(HERE / "accept_pack.py"), str(pack.root)],
                                 capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("STAGE: C2 ", bad.stdout)
        self.assertIn(f"SKILL.md names {PROPERTY} but it does not exist", bad.stdout)

    def test_scratch_follows_tempfile(self):
        with PackCopy() as pack:
            self.assertTrue(str(pack.root).startswith(tempfile.gettempdir()))

    def test_both_templates_share_the_skill_version(self):
        want = ap.skill_version((ROOT / SKILL).read_text(encoding="utf-8"))
        self.assertEqual(len(ap.REQUIRED_TEMPLATES), 2)
        for name in ap.REQUIRED_TEMPLATES:
            lines = [l for l in (ROOT / "templates" / name).read_text(encoding="utf-8").splitlines()
                     if l.lower().startswith("protocol:")]
            self.assertEqual(len(lines), 1, name)
            self.assertEqual(ap.protocol_version(lines[0]), want, name)

    def test_the_pack_ships_two_procedures_and_two_templates(self):
        self.assertEqual(sorted(p.name for p in (ROOT / "templates").glob("*.md")),
                         sorted(ap.REQUIRED_TEMPLATES))
        skill = (ROOT / SKILL).read_text(encoding="utf-8")
        for heading in ("### Review", "### Property"):
            self.assertIn(heading, skill)
        self.assertNotIn("### Comprehension", skill)

    def test_the_description_names_both_procedures_and_fits_the_limit(self):
        desc = ap.skill_description((ROOT / SKILL).read_text(encoding="utf-8"))
        self.assertIsNotNone(desc)
        self.assertLessEqual(len(desc), ap.MAX_DESCRIPTION)
        self.assertTrue(desc.endswith("."))
        self.assertIn("review", desc.lower())
        self.assertIn("property", desc.lower())

    def test_the_property_template_names_both_lanes(self):
        text = flat((ROOT / PROPERTY_TPL).read_text(encoding="utf-8")).lower()
        for phrase in ("exhaustive lane", "references/lean.md", "references/lean-handoff-example.md",
                       "by decide", "production condition", "legitimate cases", "skipped",
                       "status=skipped"):
            self.assertIn(phrase, text)

    def test_regression_cases_pass_on_the_real_pack(self):
        self.assertEqual(ap.c11_regression_cases(ROOT), [])
        self.assertEqual(ap.c18_regression_cases(ROOT), [])

    def test_check_ids_are_registered_in_order(self):
        self.assertEqual([cid for cid, _, _ in ap.CHECKS], [f"C{n}" for n in range(1, 19)])

    def test_host_gate_rejects_structural_home_paths_without_named_hosts(self):
        mutations = (
            ("/home/example-user", "absolute POSIX home path"),
            ("/Users/example-user,", "absolute POSIX home path"),
            ("/var/home/example-user.", "absolute POSIX home path"),
            ("/root", "root home path"),
            (r"C:\Users\John Smith", "Windows home path"),
            ("/mnt/c/Users/example-user", "Windows home path"),
        )
        for leaked_path, label in mutations:
            with self.subTest(leaked_path=leaked_path), PackCopy() as pack:
                pack.write(SKILL, pack.read(SKILL) + f"\nSee {leaked_path}\n")
                problems = ap.c3_host_independent(pack.root)
                self.assertTrue(any(problem.startswith(f"SKILL.md:") and label in problem
                                    for problem in problems), problems)

    def test_host_gate_allows_explicit_placeholders_and_portable_home_aliases(self):
        examples = (
            "/home/<user>/notes.md",
            "/Users/$USER/notes.md",
            r"C:\Users\%USERNAME%\notes.md",
            "~/.config/eview/settings.toml",
        )
        for example in examples:
            with self.subTest(example=example), PackCopy() as pack:
                pack.write(SKILL, pack.read(SKILL) + f"\nPortable example: {example}\n")
                self.assertEqual(ap.c3_host_independent(pack.root), [])

    def test_host_gate_scans_the_public_readme(self):
        with PackCopy() as pack:
            pack.write(README, pack.read(README) + "\nSee /home/example-user/private/notes.md.\n")
            problems = ap.c3_host_independent(pack.root)
        self.assertTrue(any(problem.startswith("README.md:") and
                            "absolute POSIX home path" in problem
                            for problem in problems), problems)

    def test_license_is_required_and_scanned_as_a_public_file(self):
        with PackCopy() as pack:
            pack.remove(LICENSE)
            self.assertIn("required LICENSE is missing", ap.c2_referenced_files(pack.root))
        with PackCopy() as pack:
            pack.write(LICENSE, pack.read(LICENSE) + "\nBuilt at /home/example-user.\n")
            problems = ap.c3_host_independent(pack.root)
        self.assertTrue(any(problem.startswith("LICENSE:") and
                            "absolute POSIX home path" in problem
                            for problem in problems), problems)


# --------------------------------------------------------- version policy mutations

class VersionTests(GateAssertions):
    def test_version_mismatch_in_the_property_template(self):
        with PackCopy() as pack:
            want = ap.skill_version(pack.read(SKILL))
            pack.sub(PROPERTY_TPL, f"protocol: eview/{want}", "protocol: eview/9.9.9")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C1",
                        f"handoff-property.md protocol line says '9.9.9', SKILL.md says '{want}'")

    def test_skill_bump_alone_names_both_templates(self):
        with PackCopy() as pack:
            want = ap.skill_version(pack.read(SKILL))
            pack.sub(SKILL, f"version: {want}", "version: 9.9.9")
            lines = ap.collect(pack.root)
        for name in ap.REQUIRED_TEMPLATES:
            self.assertDiag(lines, "C1", f"{name} protocol line says '{want}', SKILL.md says '9.9.9'")

    def test_two_protocol_lines_in_one_template(self):
        with PackCopy() as pack:
            want = ap.skill_version(pack.read(SKILL))
            pack.sub(PROPERTY_TPL, f"protocol: eview/{want}", f"protocol: eview/{want}\nprotocol: eview/{want}")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C1", "handoff-property.md has 2 `protocol:` lines, expected exactly one")

    def test_template_without_a_protocol_line(self):
        with PackCopy() as pack:
            pack.drop_lines(REVIEW_TPL, "protocol: eview/")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C1", "handoff-review.md has no `protocol:` line")

    def test_policy_counting_the_wrong_number_of_places(self):
        with PackCopy() as pack:
            pack.sub(SKILL, "exactly three places", "exactly four places")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C1", "SKILL.md says the version lives in 'four' places, but 3 carry it")

    def test_policy_sentence_removed(self):
        with PackCopy() as pack:
            pack.sub(SKILL, "lives in exactly three places", "lives in a few places")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C1", "SKILL.md states no version-places policy")

    def test_numeric_policy_count_is_accepted(self):
        with PackCopy() as pack:
            pack.sub(SKILL, "lives in exactly three places", "lives in exactly 3 places")
            self.assertEqual(ap.c1_version_consistency(pack.root), [])

    def test_other_files_must_not_restate_the_literal(self):
        for rel in (PROPERTY, LEAN, CONSUMER, README, "references/false-positive-guide.md"):
            with self.subTest(rel=rel), PackCopy() as pack:
                want = ap.skill_version(pack.read(SKILL))
                pack.write(rel, pack.read(rel) + f"\nPinned to eview/{want}.\n")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C1", f"{rel} restates a protocol version literal")

    def test_template_body_must_not_restate_the_literal(self):
        for rel in (REVIEW_TPL, PROPERTY_TPL):
            with self.subTest(rel=rel), PackCopy() as pack:
                want = ap.skill_version(pack.read(SKILL))
                pack.write(rel, pack.read(rel) + f"\nCurrently pinned to eview/{want}.\n")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C1", f"{rel} restates a protocol version literal")


class VersionLiteralBoundaryTests(GateAssertions):
    def test_literal_followed_by_sentence_punctuation_is_a_restatement(self):
        want = ap.skill_version((ROOT / SKILL).read_text(encoding="utf-8"))
        pattern = ap.version_literal_pattern(want)
        for text in (f"pinned to version {want}.", f"({want})", f"see {want};", f"eview/{want}.",
                     f"version {want}\n", want):
            with self.subTest(text=text):
                self.assertIsNotNone(pattern.search(text))

    def test_longer_unrelated_versions_are_not_a_restatement(self):
        want = ap.skill_version((ROOT / SKILL).read_text(encoding="utf-8"))
        pattern = ap.version_literal_pattern(want)
        for text in ("10.4.0", "0.4.01", "0.4.0.1", "1.0.4.0", "v10.4.0", "0.4.0x"):
            with self.subTest(text=text):
                self.assertIsNone(pattern.search(text))

    def test_an_unrelated_longer_version_is_not_flagged(self):
        with PackCopy() as pack:
            pack.write(README, pack.read(README) + "\nRequires Python 10.4.0 or newer, not 0.4.0.1.\n")
            self.assertEqual(ap.collect(pack.root), [])


# ----------------------------------------------- the removed procedure stays removed

class RemovedProcedureTests(GateAssertions):
    def test_reintroduced_protocol_file(self):
        with PackCopy() as pack:
            pack.write("references/comprehension.md", "# Comprehension\n")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C12", "references/comprehension.md still exists")

    def test_reintroduced_template_file(self):
        with PackCopy() as pack:
            pack.write("templates/handoff-comprehension.md", "# Handoff\n")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C12", "templates/handoff-comprehension.md still exists")
        self.assertDiag(lines, "C12", "templates/ holds")

    def test_reintroduced_procedure_heading(self):
        with PackCopy() as pack:
            pack.write(SKILL, pack.read(SKILL) + "\n### Comprehension\n\n1. Read the document.\n")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C12", "SKILL.md still carries a `### Comprehension` procedure")

    def test_any_third_procedure_heading_is_rejected(self):
        with PackCopy() as pack:
            pack.sub(SKILL, "### Property", "### Extra\n\n1. Do something else.\n\n### Property")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C12", "`## Procedure` has ['Review', 'Extra', 'Property']")

    def test_a_stray_mention_in_the_readme(self):
        with PackCopy() as pack:
            pack.write(README, pack.read(README) + "\nSee the comprehension notes.\n")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C12", "README.md still mentions comprehension")

    def test_a_stray_mention_in_a_reference(self):
        with PackCopy() as pack:
            pack.write(CONSUMER, pack.read(CONSUMER) + "\nUnlike the comprehension lane.\n")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C12", f"{CONSUMER} still mentions comprehension")

    def test_a_third_template(self):
        with PackCopy() as pack:
            pack.write("templates/handoff-extra.md", "protocol: eview/0.0.0\n")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C12", "templates/ holds")

    def test_skill_still_calling_them_three_siblings(self):
        with PackCopy() as pack:
            pack.sub(SKILL, "Two sibling procedures share one pack", "Three sibling procedures share one pack")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C12", "still calls the procedures `three sibling`")

    def test_readme_must_describe_two_siblings(self):
        with PackCopy() as pack:
            pack.sub(README, "two sibling procedures", "sibling procedures")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C12", "README.md does not describe two sibling procedures")

    def test_removed_test_and_fixture_paths(self):
        for rel in ("tests/test_comprehension.py", "tests/fixtures/comprehension"):
            with self.subTest(rel=rel), PackCopy() as pack:
                target = pack.root / rel
                if rel.endswith(".py"):
                    target.write_text("# old\n", encoding="utf-8")
                else:
                    target.mkdir(parents=True, exist_ok=True)
                    (target / "README.md").write_text("# old\n", encoding="utf-8")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C12", f"{rel} still exists")


# ------------------------------------------------------------ the Lean exhaustive lane

class LeanModeTests(GateAssertions):
    def mutate(self, rel: str, old: str, new: str, cid: str, fragment: str, count: int = 1):
        with PackCopy() as pack:
            pack.sub(rel, old, new, count)
            lines = ap.collect(pack.root)
        self.assertDiag(lines, cid, fragment)
        return lines

    def mutate_in(self, rel: str, heading: str, old: str, new: str, cid: str, fragment: str):
        with PackCopy() as pack:
            pack.sub_in_section(rel, heading, old, new)
            lines = ap.collect(pack.root)
        self.assertDiag(lines, cid, fragment)
        return lines

    def test_mode_heading_removed(self):
        self.mutate(PROPERTY, "## Exhaustive mode (Lean)", "## Extra lane", "C13",
                    "has no `## Exhaustive mode (Lean)` section")

    def test_by_decide_removed_from_the_mode(self):
        self.mutate_in(PROPERTY, "Exhaustive mode (Lean)", "`by decide`", "`by rfl`", "C13",
                       "that the lane closes properties with `by decide`")

    def test_lean_protocol_reference_removed(self):
        self.mutate_in(PROPERTY, "Exhaustive mode (Lean)", "references/lean.md", "the lane doc",
                       "C13", "the two files the mode requires")

    def test_read_only_constraint_removed(self):
        self.mutate_in(PROPERTY, "Exhaustive mode (Lean)", "the target is read-only",
                       "the target is writable", "C13",
                       "that the model lives outside the repository and the target stays read-only")

    def test_theorem_table_requirement_removed(self):
        self.mutate_in(PROPERTY, "Exhaustive mode (Lean)", "property / result / theorem table",
                       "summary", "C13", "the property / result / theorem table")

    def test_production_firing_condition_removed(self):
        self.mutate_in(PROPERTY, "Exhaustive mode (Lean)",
                       "production condition under which it fires", "condition",
                       "C13", "each counterexample with the production condition")

    def test_legitimate_cases_half_of_the_fix_pair_removed(self):
        self.mutate_in(PROPERTY, "Exhaustive mode (Lean)", "legitimate cases still pass",
                       "counterexample is gone", "C13",
                       "the fix predicate proved to remove the counterexample")

    def test_disabling_as_a_fix_removed(self):
        self.mutate_in(PROPERTY, "Exhaustive mode (Lean)", "disabling the behaviour is not a fix",
                       "disabling the behaviour is acceptable", "C13",
                       "the fix predicate proved to remove the counterexample")

    def test_limits_removed(self):
        self.mutate_in(PROPERTY, "Exhaustive mode (Lean)", "the limits —", "notes", "C13",
                       "the limits and the artifact path")

    def test_skip_outcome_removed(self):
        self.mutate_in(PROPERTY, "Exhaustive mode (Lean)",
                       "say `SKIPPED` and give the reason", "say something", "C13",
                       "the skip outcome and its reason")

    def test_trivially_true_guard_removed_from_the_mode(self):
        with PackCopy() as pack:
            pack.sub_in_section(PROPERTY, "Exhaustive mode (Lean)",
                                "theorem would be trivially true", "theorem would be interesting")
            pack.sub_in_section(PROPERTY, "Exhaustive mode (Lean)",
                                "A trivially true theorem is lane misuse",
                                "An interesting theorem is lane misuse")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "the skip outcome and its reason")

    def test_lane_selection_section_removed(self):
        with PackCopy() as pack:
            pack.sub(PROPERTY, "## Lane selection", "## Notes on lanes")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "has no `## Lane selection` section")

    def test_sampled_default_removed_from_lane_selection(self):
        self.mutate_in(PROPERTY, "Lane selection", "sampled lane is the default",
                       "sampled lane is optional", "C13",
                       "the finite-map test that makes the exhaustive lane available")

    def test_finite_map_test_removed_from_lane_selection(self):
        self.mutate_in(PROPERTY, "Lane selection", "Run a finite-map test on the diff first.",
                       "Look at the diff.", "C13",
                       "the finite-map test that makes the exhaustive lane available")

    def test_each_lane_token_is_pinned(self):
        for token in ("`LANE=sampled`", "`LANE=exhaustive`", "`LANE=auto`"):
            with self.subTest(token=token), PackCopy() as pack:
                pack.sub_in_section(PROPERTY, "Lane selection", token, "`LANE=other`")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C13", "the handoff's sampled, exhaustive and auto lane-token semantics")

    def test_exhaustive_preconditions_do_not_require_the_sampled_runtime(self):
        with PackCopy() as pack:
            pack.sub_in_section(PROPERTY, "Preconditions",
                                "does not require the repository runtime or a property library",
                                "requires the repository runtime and a property library")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "lane-specific dependencies rather than a sampled-only global prerequisite")

    def test_exhaustive_environment_does_not_require_a_property_library(self):
        with PackCopy() as pack:
            pack.sub_in_section(PROPERTY, "0. Environment",
                                "does not require a property library or repository runtime",
                                "requires a property library and repository runtime", level="###")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "lane-specific setup without a property-library requirement")

    def test_exhaustive_lane_skips_the_sampled_test_steps(self):
        with PackCopy() as pack:
            pack.sub_in_section(PROPERTY, "Procedure",
                                "The exhaustive lane skips those sampled-only steps",
                                "The exhaustive lane also runs those steps")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "that exhaustive-only work skips the sampled-test steps")

    def test_sampled_return_subsection_is_required(self):
        with PackCopy() as pack:
            pack.sub(PROPERTY, "### Sampled-mode return", "### Sampling notes")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "has no `### Sampled-mode return` subsection")

    def test_sampled_return_fields_are_pinned(self):
        for old in ("`## Findings`", "`## No-counterexample summary`", "`## Carried / unverified`"):
            with self.subTest(old=old), PackCopy() as pack:
                pack.sub_in_section(PROPERTY, "Sampled-mode return", old, "`## Something else`",
                                    level="###")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C13", "the sampled header, findings, no-counterexample, carried and notes schema")

    def test_sampled_header_requires_the_exact_lane_field(self):
        with PackCopy() as pack:
            pack.sub_in_section(PROPERTY, "Sampled-mode return", "| lane=sampled |",
                                "| lane=sampled+exhaustive |", level="###")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "has no exact `| lane=sampled |` header field")

    def test_sampled_disclaimer_is_pinned(self):
        with PackCopy() as pack:
            pack.sub_in_section(PROPERTY, "Sampled-mode return", ap.SAMPLED_DISCLAIMER,
                                "Sampling passed.", level="###")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "the sampling-not-assurance disclaimer")

    def test_skill_entry_point_keeps_the_sampled_return_contract(self):
        with PackCopy() as pack:
            pack.sub_in_section(SKILL, "Property", "sampling-not-assurance line",
                                "success line", level="###")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "the default sampled return and the skipped exhaustive return")

    def test_skill_entry_point_keeps_sampled_as_the_default(self):
        with PackCopy() as pack:
            pack.sub_in_section(SKILL, "Property", "**sampled** (default)",
                                "**sampled** (optional)", level="###")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "the default sampled return and the skipped exhaustive return")

    def test_exhaustive_return_subsection_removed(self):
        with PackCopy() as pack:
            pack.sub(PROPERTY, "### Exhaustive-mode return", "### Lane notes")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "has no `### Exhaustive-mode return` subsection")

    def test_exhaustive_return_table_header_changed(self):
        with PackCopy() as pack:
            pack.sub_in_section(PROPERTY, "Exhaustive-mode return", "| property | result | theorem |",
                                "| item | result | theorem |", level="###")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "the table header")

    def test_exhaustive_return_does_not_inherit_the_sampling_disclaimer(self):
        with PackCopy() as pack:
            pack.sub_in_section(PROPERTY, "Exhaustive-mode return",
                                "The sampled-lane mandatory line applies when sampling also ran. "
                                "Do not append the sampling disclaimer to an exhaustive-only return.",
                                "The sampled-lane mandatory line always applies.", level="###")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "that the sampling disclaimer applies only when sampling ran")

    def test_property_template_scopes_the_disclaimer_by_lane(self):
        with PackCopy() as pack:
            pack.sub_in_section(PROPERTY_TPL, "Output", "Do not append the sampling disclaimer",
                                "Append the sampling disclaimer")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "separate sampled, exhaustive-only, skipped and combined output rules")

    def test_exhaustive_header_is_proof_scoped_not_sample_scoped(self):
        for old in ("does not carry meaningless `seeds` or", "does not verify the source system"):
            with self.subTest(old=old), PackCopy() as pack:
                pack.sub_in_section(PROPERTY, "Exhaustive-mode return", old, "says nothing", level="###")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C13", "an exhaustive-only header without sampled fields")

    def test_skipped_return_subsection_is_required(self):
        with PackCopy() as pack:
            pack.sub(PROPERTY, "### Skipped exhaustive return", "### Skip notes")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C13", "has no `### Skipped exhaustive return` subsection")

    def test_skipped_return_has_schema_evidence_and_artifact_waiver(self):
        for old, fragment in (("status=SKIPPED", "a caller-parseable skip-only schema"),
                              ("evidence: <file/range inspected>", "a caller-parseable skip-only schema"),
                              ("lane did not execute", "the skipped-lane waiver"),
                              ("If sampling also ran", "the skipped-lane waiver")):
            with self.subTest(old=old), PackCopy() as pack:
                pack.sub_in_section(PROPERTY, "Skipped exhaustive return", old, "something",
                                    level="###")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C13", fragment)

    def test_skipped_schema_requires_case_and_real_fenced_headings(self):
        for old, new, fragment in (("| status=SKIPPED", "| status=skipped",
                                    "case-sensitive status field"),
                                   ("\n## Notes\n", "\n## Commentary\n",
                                    "Notes section in the schema block")):
            with self.subTest(old=old), PackCopy() as pack:
                pack.sub_in_section(PROPERTY, "Skipped exhaustive return", old, new, level="###")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C13", fragment)

    def test_property_template_pins_auto_and_combined_lane_semantics(self):
        for heading, old, new, fragment in (
            ("Inputs", "`auto` lets the worker apply the finite-map test",
             "`auto` does something", "the sampled, exhaustive and auto lane tokens plus auto semantics"),
            ("Output", "Both lanes — include both schemas", "Both lanes — choose one schema",
             "separate sampled, exhaustive-only, skipped and combined output rules"),
        ):
            with self.subTest(heading=heading), PackCopy() as pack:
                pack.sub_in_section(PROPERTY_TPL, heading, old, new)
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C13", fragment)


class LeanFileTests(GateAssertions):
    def test_missing_lean_protocol(self):
        with PackCopy() as pack:
            pack.remove(LEAN)
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C2", f"SKILL.md names {LEAN} but it does not exist")
        self.assertDiag(lines, "C14", f"{LEAN} is missing")

    def test_missing_lean_example(self):
        with PackCopy() as pack:
            pack.remove(LEAN_EXAMPLE)
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C2", f"SKILL.md names {LEAN_EXAMPLE} but it does not exist")
        self.assertDiag(lines, "C14", f"{LEAN_EXAMPLE} is missing")

    def test_each_lean_section_is_pinned(self):
        for heading in ("When to use it", "When to skip it", "Procedure", "Environment",
                        "Pitfalls", "Acceptance", "Skipped return"):
            with self.subTest(heading=heading), PackCopy() as pack:
                pack.sub(LEAN, f"## {heading}", f"## About {heading}")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C14", f"has no `## {heading}` section")

    def test_skip_conditions_removed(self):
        with PackCopy() as pack:
            pack.sub_in_section(LEAN, "When to skip it", "The theorem would be trivially true",
                                "The theorem would be interesting")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C14", "the skip conditions")

    def test_procedure_loses_the_language_neutral_extraction_or_the_fix_pair(self):
        for old in ("language-native parser or AST", "smallest compilable slice",
                    "applies equally to Python, JS/TS, Rust, Go",
                    "minimal counterexample", "legitimate cases still pass"):
            with self.subTest(old=old), PackCopy() as pack:
                pack.sub_in_section(LEAN, "Procedure", old, "something")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C14", "the transcription steps, the decide close and the fix pair")

    def test_environment_loses_elan(self):
        with PackCopy() as pack:
            pack.sub_in_section(LEAN, "Environment", "elan toolchain install", "install lean")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C14", "the Lean 4 core environment")

    def test_recursion_depth_pitfall_removed(self):
        with PackCopy() as pack:
            pack.sub_in_section(LEAN, "Pitfalls", "set_option maxRecDepth 20000", "")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C14", "the measured pitfalls of the lane")

    def test_acceptance_items_removed(self):
        for old in ("production condition", "legitimate cases still pass", "limits", "absolute path",
                    "When the skip test fires", "not required because the lane did not run"):
            with self.subTest(old=old), PackCopy() as pack:
                pack.sub_in_section(LEAN, "Acceptance", old, "something")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C14", "the executed-lane acceptance items and skipped-lane waiver")

    def test_skipped_return_schema_removed(self):
        for old in ("status=SKIPPED", "file/range evidence", "Do not emit theorem results or a Lean artifact"):
            with self.subTest(old=old), PackCopy() as pack:
                pack.sub_in_section(LEAN, "Skipped return", old, "something")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C14", "the skip-only schema, evidence and artifact waiver")

    def test_example_loses_the_return_table(self):
        with PackCopy() as pack:
            pack.sub(LEAN_EXAMPLE, "| property | result | theorem |", "| item | result | theorem |")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C14", "the handoff fields, the return table")

    def test_example_loses_the_fix_pair_or_limits(self):
        for old in ("legitimate cases still pass", "**Limits**", "absolute `.lean` path", "`lake build`"):
            with self.subTest(old=old), PackCopy() as pack:
                pack.sub(LEAN_EXAMPLE, old, "something", count=0)
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C14", "the handoff fields, the return table")

    def test_example_loses_conditional_paths_or_skip_schema(self):
        for old in ("<THROWAWAY_ABS>", "only when `RUN_ABS` was supplied",
                    "otherwise return it on stdout", "status=SKIPPED",
                    "No `.lean` artifact or `lake build` result is required"):
            with self.subTest(old=old), PackCopy() as pack:
                pack.sub(LEAN_EXAMPLE, old, "something", count=0)
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C14", "conditional artifact destinations and the complete skip-only return")

    def test_example_loses_the_read_only_constraint(self):
        with PackCopy() as pack:
            pack.sub(LEAN_EXAMPLE, "Read-only on the target repository", "Write freely in the repository")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C14", "that the target repository is read-only")


# --------------------------------------------- the firing rule across stating files

class FiringConditionTests(GateAssertions):
    def test_skill_pitfalls_lose_the_rule(self):
        with PackCopy() as pack:
            pack.sub_in_section(SKILL, "Pitfalls",
                                "A counterexample that cannot fire in production is not a finding", "")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C15", f"{SKILL} `## Pitfalls` does not state that a "
                                      "counterexample that cannot fire in production is not a finding")

    def test_property_pitfalls_lose_the_rule(self):
        with PackCopy() as pack:
            pack.sub_in_section(PROPERTY, "Pitfalls",
                                "A counterexample that cannot fire in production is not a finding", "")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C15", f"{PROPERTY} `## Pitfalls` does not state")

    def test_lean_pitfalls_lose_the_rule(self):
        with PackCopy() as pack:
            pack.sub_in_section(LEAN, "Pitfalls",
                                "A counterexample that cannot fire in production is not a finding", "")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C15", f"{LEAN} `## Pitfalls` does not state")

    def test_a_file_without_the_firing_condition_instruction(self):
        with PackCopy() as pack:
            pack.sub_in_section(SKILL, "Pitfalls", "State the firing condition", "Mention it")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C15", f"{SKILL} `## Pitfalls` does not say to state the firing condition")

    def test_identity_rule_removed_from_the_lane_protocol(self):
        with PackCopy() as pack:
            pack.sub_in_section(LEAN, "Pitfalls", '"Uniqueness holds" is not "identity holds"',
                                '"Uniqueness holds" is not "coverage holds"')
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C15", f"{LEAN} `## Pitfalls` does not state that uniqueness is not identity")

    def test_identity_rule_removed_from_the_property_protocol(self):
        with PackCopy() as pack:
            pack.sub_in_section(PROPERTY, "Pitfalls", '"Uniqueness holds" is not "identity holds"',
                                '"Uniqueness holds" is not "coverage holds"')
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C15", f"{PROPERTY} `## Pitfalls` does not state that uniqueness is not identity")

    def test_identity_rule_removed_from_the_skill_entry_point(self):
        with PackCopy() as pack:
            pack.sub_in_section(SKILL, "Pitfalls", '"Uniqueness holds" is not "identity holds"',
                                '"Uniqueness holds" is not "coverage holds"')
            # Leave the word elsewhere to prove C15 checks the rule in Pitfalls, not a file substring.
            pack.write(SKILL, pack.read(SKILL) + "\nIdentity is discussed elsewhere.\n")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C15", f"{SKILL} `## Pitfalls` does not state that uniqueness is not identity")

    def test_identity_action_is_pinned_in_each_pitfalls_section(self):
        for rel in (SKILL, PROPERTY, LEAN):
            with self.subTest(rel=rel), PackCopy() as pack:
                pack.sub_in_section(rel, "Pitfalls", "what it prevents", "what it selects")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C15", f"{rel} `## Pitfalls` does not state the identity gate's coverage")

    def test_proof_scope_rule_is_pinned_in_every_public_surface(self):
        for rel in ap.PROOF_SCOPE_FILES:
            with self.subTest(rel=rel), PackCopy() as pack:
                pack.sub(rel, ap.PROOF_SCOPE_RULE, "The proof verifies everything.", count=0)
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C15", f"{rel} does not state the proof-scope rule")


# ----------------------------------------------------- report-consumer validation

class ReportConsumerTests(GateAssertions):
    def test_the_rule_table_is_pinned_independently(self):
        # Written out here so an emptied or shortened C16 table cannot make the loop below
        # vacuous.
        self.assertEqual({label for label, _ in ap.CONSUMER_RULES},
                         {"the schema-first refusal", "row-by-row reconciliation",
                          "raw count versus deduplicated count",
                          "both healthy and nonclean fixtures",
                          "sampled, exhaustive and skipped property fixtures",
                          "rejected evidence is preserved", "a local repair stays local",
                          "that it is not a third procedure"})

    def test_missing_doc(self):
        with PackCopy() as pack:
            pack.remove(CONSUMER)
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C2", f"SKILL.md names {CONSUMER} but it does not exist")
        self.assertDiag(lines, "C16", f"{CONSUMER} is missing")

    def test_each_rule_is_pinned(self):
        for label, phrase in ap.CONSUMER_RULES:
            with self.subTest(label=label), PackCopy() as pack:
                text = pack.read(CONSUMER)
                pattern = re.compile(r"\s+".join(re.escape(w) for w in phrase.split()))
                self.assertRegex(text, pattern)
                pack.write(CONSUMER, pattern.sub("Something else", text, count=1))
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C16", f"{CONSUMER} does not state {label}")

    def test_skill_must_name_the_doc(self):
        with PackCopy() as pack:
            pack.sub(SKILL, f"`{CONSUMER}`", "`a-consumer-doc.md`", count=0)
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C16", f"SKILL.md does not name {CONSUMER}")

    def test_readme_must_list_the_doc(self):
        with PackCopy() as pack:
            pack.sub(README, f"`{CONSUMER}`", "`a-consumer-doc.md`", count=0)
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C16", f"README.md does not list {CONSUMER}")


# ------------------------------------------------------------ README invocations

class ReadmeTests(GateAssertions):
    def test_gate_command_removed(self):
        with PackCopy() as pack:
            pack.sub(README, ap.GATE_COMMAND, "python3 tests/run.py")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C17", "does not give the gate invocation")

    def test_test_command_removed(self):
        with PackCopy() as pack:
            pack.sub(README, ap.TEST_COMMAND, "python3 -m unittest")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C17", "does not give the test invocation")

    def test_pack_ok_explanation_removed(self):
        with PackCopy() as pack:
            pack.sub(README, "PACK_OK", "a success line")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C17", "does not say the gate prints PACK_OK on success")

    def test_readme_names_a_missing_test_file(self):
        with PackCopy() as pack:
            pack.write(README, pack.read(README) + "\npython3 tests/test_missing.py\n")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C17", "README.md names tests/test_missing.py but it does not exist")

    def test_an_unlisted_test_file(self):
        with PackCopy() as pack:
            (pack.root / "tests/test_extra.py").write_text("# extra\n", encoding="utf-8")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C17", "tests/test_extra.py is not listed in README.md")

    def test_the_two_template_bump_sentence_removed(self):
        with PackCopy() as pack:
            pack.sub(README, "in **both** templates", "in the templates")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C17", "does not say the version bump reaches both templates")


# --------------------------------------------------------- previous-report plumbing

class LegacyPreviousReportTests(GateAssertions):
    def test_review_template_loses_its_previous_report_line(self):
        with PackCopy() as pack:
            pack.drop_lines(REVIEW_TPL, "previous report")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C5", "handoff-review.md has no `previous report` line")

    def test_property_template_loses_its_previous_report_line(self):
        with PackCopy() as pack:
            pack.drop_lines(PROPERTY_TPL, "previous report")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C5", "handoff-property.md has no `previous report` line")

    def test_previous_report_line_without_an_absolute_path_sample(self):
        with PackCopy() as pack:
            pack.sub(REVIEW_TPL, "absolute path to one file (e.g. `/abs/dir/report.md`),",
                     "a file, e.g. `report.md`,")
            pack.sub(REVIEW_TPL,
                     "never a directory or a relative path: `<PREVIOUS_REPORT_ABS or none>`",
                     "`<PREVIOUS_REPORT or none>`")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C5", "handoff-review.md `previous report` line carries no absolute path sample")

    def test_a_missing_template_fails_instead_of_being_skipped(self):
        for name in ap.REQUIRED_TEMPLATES:
            with self.subTest(name=name), PackCopy() as pack:
                pack.remove(f"templates/{name}")
                lines = ap.collect(pack.root)
            self.assertDiag(lines, "C5", f"templates/{name} is missing")
            self.assertDiag(lines, "C1", f"templates/{name} is missing")


# --------------------------------------------------------------- description limit

class DescriptionTests(GateAssertions):
    def description_of(self, pack: "PackCopy") -> str:
        return ap.skill_description(pack.read(SKILL))

    def test_overlong_description_is_rejected(self):
        with PackCopy() as pack:
            old = self.description_of(pack)
            pack.sub(SKILL, old, old[:-1] + " whenever a general review or property pass is needed.")
            lines = ap.collect(pack.root)
        self.assertDiag(lines, "C12", "over the 60 limit")

    def test_exactly_at_the_limit_passes_and_one_over_fails(self):
        with PackCopy() as pack:
            old = self.description_of(pack)
            at_limit = ("Use for review and property: " + "x" * 60)[:59] + "."
            self.assertEqual(len(at_limit), 60)
            pack.sub(SKILL, old, at_limit)
            self.assertEqual(ap.c12_two_procedures(pack.root), [])
            pack.sub(SKILL, at_limit, at_limit[:-1] + "x.")
            self.assertTrue(any("61 characters" in p for p in ap.c12_two_procedures(pack.root)))

    def test_description_without_a_period_or_a_procedure_name(self):
        with PackCopy() as pack:
            old = self.description_of(pack)
            pack.sub(SKILL, old, old[:-1])
            self.assertIn("SKILL.md description does not end in a period",
                          ap.c12_two_procedures(pack.root))
        for word in ("review", "property"):
            with self.subTest(word=word), PackCopy() as pack:
                old = self.description_of(pack)
                pack.sub(SKILL, old, "Use for something else entirely.")
                self.assertIn(f"SKILL.md description does not mention {word}",
                              ap.c12_two_procedures(pack.root))


if __name__ == "__main__":
    unittest.main(verbosity=1)
