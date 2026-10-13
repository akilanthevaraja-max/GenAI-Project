# Juniper Cafe prototype appendix

## Design rationale

- **User and workflow:** a Juniper Cafe manager preparing the weekly operations meeting uploads a feedback batch, reviews a traceable briefing, inspects evidence, and decides whether to investigate.
- **5A choice:** Automation + Assistant. The repeatable ingestion, deduplication, counting, validation, and export are automated; the interface assists a human decision rather than acting autonomously.
- **EDGE target:** Decisions. The target is a more accurate, relevant, and auditable operations briefing, with preparation time as a secondary efficiency measure.
- **Observation unit:** one `visit_id`. Multiple messages from one visit retain every feedback ID but contribute one observation to denominators.
- **Deterministic boundary:** Python/Pandas owns parsing, duplicate handling, unique-visit denominators, branch counts, theme counts after classification, validation, and export.
- **GenAI boundary:** a configurable LLM assigns multi-label themes and mixed sentiment, then drafts prose from locked deterministic aggregates. A validator rejects invented references or ratios.
- **Human control:** the manager checks source comments and theme labels, judges operational feasibility, and makes the final decision. The application does not infer causes or trigger actions.
- **Trade-offs:** a fixed theme taxonomy improves comparability and validation but may miss a new theme. Offline rules make the demo resilient but are less semantically capable than a model. Multi-label counts correctly need not sum to the denominator.

## Reproduction

Use Python 3.10 or later. Install `requirements.txt`, then run `python -m streamlit run app.py`. The starter CSV is in `data/starter_feedback.csv`. OpenRouter uses its OpenAI-compatible endpoint and accepts a configurable model string; direct Anthropic is included because the supplied credential is an Anthropic key. Offline demo mode requires no API. The application never stores a pasted key.

**Group members and contributions:** replace this line before submission with the group member name(s) and a truthful contribution summary. Current implementation contribution: prototype architecture, Python pipeline, Streamlit interface, validation, tests, and PDF export.

## Compact test evidence

The automated suite contains 19 checks. Baseline means manual reading or a single unconstrained prompt; its outcomes are estimated because no timed human study was supplied.

| # | Input or condition | Expected behaviour | Baseline result (estimated) | Prototype result | Judgment |
|---|---|---|---|---|---|
| 1 | Starter batch | Load all 12 messages | Usually loads | 12 loaded | Pass |
| 2 | F03/F07 repeat V03 | Count one visit, retain both IDs | Easy to double-count | 11 visits; both IDs retained | Pass |
| 3 | Combined `ID / visit` header | Parse source format | Manual cleanup | Parsed | Pass |
| 4 | Headers only | Explain empty batch | Prompt may invent output | Blocked with clear error | Pass |
| 5 | Missing branch column | Explain missing field | Late failure | Blocked with exact field | Pass |
| 6 | Repeated feedback ID | Prevent ambiguous evidence | Often unnoticed | Blocked with repeated ID | Pass |
| 7 | Two distinct messages, same visit | Merge evidence, count once | Inconsistent | Merged and labelled | Pass |
| 8 | Conflicting branches, same visit | Expose ambiguity | Often hidden | Warning; first branch documented | Pass |
| 9 | Multi-theme comment | Apply several themes | Single sentiment loses detail | Multiple labels retained | Pass |
| 10 | Theme denominators | Always use N = unique visits | Prompt arithmetic risk | Every denominator is 11 | Pass |
| 11 | Praise plus complaint | Mark mixed | Positive/negative collapse | Mixed flag | Pass |
| 12 | `Disappointing.` | Avoid invented operational cause | Prompt may speculate | Low-detail theme | Pass |
| 13 | Brief structure | Sample caveat, evidence, one investigation | Variable | Validator accepts | Pass |
| 14 | Hallucinated source ID | Reject | Hard to detect manually | Validator rejects | Pass |
| 15 | Invented ratio | Reject | Arithmetic risk | Validator rejects | Pass |
| 16 | PDF export | Readable file with review footer | Manual formatting | Parsed successfully | Pass |
| 17 | Initial Streamlit screen | Render starter metrics without an exception | Manual setup risk | 12 / 11 / 1 shown | Pass |
| 18 | End-to-end interface run | Generate results, tabs and both downloads | Variable | Completed without exception | Pass |
| 19 | Anthropic model selector | Offer current Claude models without exposing a key | Manual model-ID entry | Haiku, Sonnet, Opus and Fable available | Pass |

## Results, cost, and limitations

- **Quality:** 19/19 automated conditions pass in the included environment. These are engineering checks, not a claim of real-world managerial impact.
- **Time:** the offline pipeline is intended to run in seconds; API latency depends on provider and model. Manual baseline time was not measured.
- **Cost:** offline mode costs no API tokens. Live cost is unavailable until a chosen model processes a measured batch; provider pricing and token usage should be recorded during the demo.
- **Sampling limitation:** feedback is a convenience sample with no total customer count, sales volume, response rate, or staffing records.
- **Model limitation:** semantic labels can still be wrong. The evidence explorer and deterministic fallback keep the manager in control.
- **Next improvement:** collect manager corrections to theme labels and evaluate agreement, factual support, preparation time, and per-batch token cost on a larger labelled set.

## Suggested 3-5 minute demo

1. State the manager problem, Automation + Assistant choice, and Decisions target.
2. Run the starter batch and show 12 messages becoming 11 visits, with F03/F07 retained together.
3. Open the evidence explorer, show a mixed multi-theme visit, then download Markdown and PDF.
4. Upload an empty or malformed file to show a safe failure.
5. Summarise the test table, sampling limitation, human review, and next improvement.
