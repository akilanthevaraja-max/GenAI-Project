from __future__ import annotations

import io
import unittest
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from juniper.briefing import build_deterministic_briefing, validate_briefing
from juniper.core import (
    InputValidationError,
    compute_aggregates,
    deduplicate_visits,
    heuristic_classify,
    load_feedback,
)
from juniper.pdf_export import briefing_to_pdf


ROOT = Path(__file__).resolve().parents[1]


class JuniperTests(unittest.TestCase):
    def setUp(self):
        self.messages = load_feedback(str(ROOT / "data" / "starter_feedback.csv"))
        self.dedupe = deduplicate_visits(self.messages)
        self.classifications = heuristic_classify(self.dedupe.visits)
        self.aggregates = compute_aggregates(
            self.dedupe.visits, self.classifications, len(self.messages)
        )

    def test_starter_has_expected_message_count(self):
        self.assertEqual(len(self.messages), 12)

    def test_starter_deduplicates_to_unique_visits(self):
        self.assertEqual(len(self.dedupe.visits), 11)
        v03 = self.dedupe.visits.set_index("visit_id").loc["V03"]
        self.assertEqual(v03.source_feedback_ids, ("F03", "F07"))

    def test_combined_id_column_is_parsed(self):
        csv = io.StringIO('ID / visit,Branch,Comment\nF20 / V20,Central,"Good coffee"\n')
        result = load_feedback(csv)
        self.assertEqual(result.loc[0, "feedback_id"], "F20")
        self.assertEqual(result.loc[0, "visit_id"], "V20")

    def test_empty_batch_is_rejected(self):
        with self.assertRaises(InputValidationError):
            load_feedback(io.StringIO("feedback_id,visit_id,branch,comment\n"))

    def test_missing_column_is_rejected(self):
        with self.assertRaises(InputValidationError):
            load_feedback(io.StringIO("feedback_id,visit_id,comment\nF1,V1,Hello\n"))

    def test_repeated_feedback_id_is_rejected(self):
        csv = io.StringIO(
            "feedback_id,visit_id,branch,comment\nF1,V1,A,One\nF1,V2,A,Two\n"
        )
        with self.assertRaises(InputValidationError):
            load_feedback(csv)

    def test_distinct_messages_for_one_visit_are_merged(self):
        frame = pd.DataFrame(
            [
                {"feedback_id": "F1", "visit_id": "V1", "branch": "A", "comment": "Slow."},
                {"feedback_id": "F2", "visit_id": "V1", "branch": "A", "comment": "Friendly."},
            ]
        )
        result = deduplicate_visits(frame)
        self.assertIn("[F1] Slow.", result.visits.loc[0, "comment"])
        self.assertIn("[F2] Friendly.", result.visits.loc[0, "comment"])

    def test_branch_conflict_is_exposed(self):
        frame = pd.DataFrame(
            [
                {"feedback_id": "F1", "visit_id": "V1", "branch": "A", "comment": "One"},
                {"feedback_id": "F2", "visit_id": "V1", "branch": "B", "comment": "Two"},
            ]
        )
        result = deduplicate_visits(frame)
        self.assertEqual(len(result.warnings), 1)

    def test_multilabel_visit_counts_in_each_theme(self):
        theme_counts = {item["theme"]: item["visits"] for item in self.aggregates["themes"]}
        self.assertEqual(theme_counts["Cleanliness and seating"], 2)
        self.assertEqual(theme_counts["Service and friendliness"], 4)

    def test_all_denominators_use_unique_visits(self):
        denominators = [item["denominator"] for item in self.aggregates["themes"]]
        denominators += [item["denominator"] for item in self.aggregates["branches"]]
        self.assertEqual(set(denominators), {11})

    def test_mixed_feedback_is_flagged(self):
        classified = self.classifications.set_index("visit_id")
        self.assertEqual(classified.loc["V01", "sentiment"], "mixed")

    def test_low_detail_feedback_is_not_invented(self):
        classified = self.classifications.set_index("visit_id")
        self.assertEqual(
            classified.loc["V11", "themes"], ["Unclear or little usable detail"]
        )

    def test_briefing_has_sample_context_evidence_and_one_investigation(self):
        briefing = build_deterministic_briefing(self.aggregates)
        self.assertIn("convenience sample", briefing)
        self.assertIn("[F03/F07/V03]", briefing)
        self.assertEqual(briefing.count("## Recommended investigation (exactly one)"), 1)
        self.assertEqual(validate_briefing(briefing, self.aggregates), [])

    def test_validator_rejects_unknown_evidence(self):
        briefing = build_deterministic_briefing(self.aggregates) + "\n[F99/V99]"
        self.assertTrue(any("Unknown evidence" in error for error in validate_briefing(briefing, self.aggregates)))

    def test_validator_rejects_invented_ratio(self):
        briefing = build_deterministic_briefing(self.aggregates) + "\n9/11"
        self.assertTrue(any("Unsupported ratio" in error for error in validate_briefing(briefing, self.aggregates)))

    def test_pdf_is_readable_and_contains_footer(self):
        briefing = build_deterministic_briefing(self.aggregates)
        pdf = briefing_to_pdf(briefing)
        self.assertTrue(pdf.startswith(b"%PDF"))
        reader = PdfReader(io.BytesIO(pdf))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("Juniper Cafe", text)
        self.assertIn("Manager review required", text)


if __name__ == "__main__":
    unittest.main()
