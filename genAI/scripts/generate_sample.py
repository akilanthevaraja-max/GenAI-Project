"""Generate the verified starter-batch PDF used as a submission example."""

from pathlib import Path

from juniper.briefing import build_deterministic_briefing
from juniper.core import compute_aggregates, deduplicate_visits, heuristic_classify, load_feedback
from juniper.pdf_export import briefing_to_pdf


ROOT = Path(__file__).resolve().parents[1]
messages = load_feedback(str(ROOT / "data" / "starter_feedback.csv"))
dedupe = deduplicate_visits(messages)
classifications = heuristic_classify(dedupe.visits)
aggregates = compute_aggregates(dedupe.visits, classifications, len(messages))
briefing = build_deterministic_briefing(aggregates)
(ROOT / "output" / "pdf" / "juniper_starter_briefing.pdf").write_bytes(
    briefing_to_pdf(briefing)
)
