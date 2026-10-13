# Juniper Cafe operations briefing app

A Streamlit prototype that converts a CSV feedback batch into a traceable Markdown briefing and downloadable PDF. The observation unit is the **visit**, so repeated messages from the same `visit_id` are merged before any count is calculated.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m streamlit run app.py
```

The Case 04 starter batch loads automatically. To use an API, select **OpenRouter** or **Anthropic** in the sidebar, enter a model string and paste the key into the password field. Keys are not written by the application. You can instead set `OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY`, or copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add the secret locally.

CSV columns:

```text
feedback_id,visit_id,branch,comment
```

The combined source format `ID / visit,Branch,Comment` is also accepted.

## Pipeline

1. Pandas validates the CSV and groups rows by `visit_id`.
2. A model (or transparent offline rules) assigns multi-label themes and mixed sentiment at visit level.
3. Python computes exact theme, branch, and sentiment aggregations using the unique-visit denominator.
4. A model drafts the Markdown briefing from only those aggregates.
5. Python validates evidence references, ratios, sampling language, and the single investigation requirement. Invalid drafts fall back to a deterministic briefing.
6. ReportLab converts the accepted Markdown into a downloadable PDF.

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

See [APPENDIX.md](APPENDIX.md) for design rationale, test evidence, limitations, and demo guidance.
