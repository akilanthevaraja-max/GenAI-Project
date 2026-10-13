# Project Brief: Juniper Café Operations Briefing App

## 1. Objective
Build a Streamlit application where a manager uploads a customer feedback batch and receives a traceable, evidence-linked Markdown operations briefing along with a downloadable PDF export.

## 2. Core Architectural Decisions
* **5A Framework & Target:** **Automation + Assistant** focused on **Decisions**.
* **Observation Unit:** The **Visit** (`visit_id`), not the message (`feedback_id`).
* **Deterministic Boundary (Python/Pandas):**
  * Parses uploads and deduplicates repeated visits (e.g., merging `F07`/`V03` into `F03`/`V03`).
  * Calculates exact denominators ($N = \text{unique visits}$) and branch breakdowns.
* **GenAI Boundary (OpenRouter LLM):**
  * Tags multi-label operational themes and flags conflicting/mixed sentiments.
  * Generates the executive briefing grounded in deterministic numbers.
* **Pipeline Separation:** Two-step flow to ensure count accuracy:
  1. Structured theme classification per unique visit.
  2. Synthesis of pre-computed aggregations into a finalized briefing.

## 3. Key Briefing Requirements
* **Accurate Denominators:** Frequencies formatted strictly as $\frac{\text{Visits}}{\text{Total Unique Visits}}$ (percentages do not need to sum to 100%).
* **Traceable Evidence:** Every insight must reference original IDs (e.g., `[F01/V01]`).
* **Sampling Context:** Explicitly note that feedback is a convenience sample without total customer or sales volume context.
* **Actionable Hypothesis:** Suggest exactly **one** small operational investigation and outline the extra data required to test it.

## 4. Stack & Deliverables
* **Frontend:** Streamlit with CSV upload and PDF download functionality.
* **LLM Integration:** OpenRouter (OpenAI-compatible client) with a configurable model string.
* **PDF Generation:** Lightweight pure-Python library (e.g., `markdown-pdf`).
* **Starter Data:** Pre-load the Case 04 starter batch for instant demonstration.