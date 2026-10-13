from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from packaging.version import Version

from juniper.briefing import build_deterministic_briefing, validate_briefing
from juniper.core import (
    InputValidationError,
    compute_aggregates,
    deduplicate_visits,
    heuristic_classify,
    load_feedback,
)
from juniper.llm import LLMClient
from juniper.pdf_export import briefing_to_pdf


ROOT = Path(__file__).resolve().parent
STARTER = ROOT / "data" / "starter_feedback.csv"
ANTHROPIC_MODELS = {
    "claude-haiku-5-5": "Claude Haiku 5.5 - rapide, recommandé",
    "claude-sonnet-5-5": "Claude Sonnet 5.5 - équilibre qualité/vitesse",
    "claude-opus-5-5": "Claude Opus 5.5 - analyse avancée",
    "claude-fable-5-1": "Claude Fable 5.1 - raisonnement exigeant",
}
STRETCH = (
    {"width": "stretch"}
    if Version(st.__version__) >= Version("1.54.0")
    else {"use_container_width": True}
)


def get_secret(name: str) -> str:
    """Read a local secret without making it mandatory for offline mode."""
    value = os.getenv(name, "")
    try:
        return str(st.secrets.get(name, value))
    except Exception:
        return value


def batch_fingerprint(messages: pd.DataFrame) -> str:
    stable_csv = messages.sort_values("feedback_id").to_csv(index=False)
    return hashlib.sha256(stable_csv.encode("utf-8")).hexdigest()


st.set_page_config(
    page_title="Juniper Cafe | Operations briefing",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --juniper-900: #173b33;
        --juniper-700: #285e4f;
        --juniper-500: #4d806e;
        --paper: #fffdf8;
        --line: #dce5df;
        --ink: #18302b;
        --muted: #60736d;
    }
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, #f6f2e9 0, #fffdf8 260px, #fffdf8 100%);
        color: var(--ink);
    }
    [data-testid="stHeader"] { background: transparent; }
    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }
    [data-testid="stSidebar"] {
        background: #eef3ef;
        border-right: 1px solid #d9e3dc;
    }
    [data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }
    .hero {
        background: linear-gradient(125deg, #173b33 0%, #245a4c 72%, #ad7848 140%);
        border-radius: 24px;
        padding: 2.15rem 2.35rem;
        color: white;
        box-shadow: 0 18px 44px rgba(23, 59, 51, .16);
        margin-bottom: 1.35rem;
    }
    .hero__topline {
        display: flex;
        align-items: center;
        gap: .65rem;
        margin-bottom: 1rem;
        font-size: .78rem;
        font-weight: 750;
        letter-spacing: .09em;
        text-transform: uppercase;
        color: #d7e8e0;
    }
    .hero__dot { width: 8px; height: 8px; border-radius: 50%; background: #efb56f; }
    .hero h1 {
        margin: 0;
        max-width: 760px;
        font-size: clamp(2rem, 4vw, 3.25rem);
        line-height: 1.03;
        letter-spacing: -.035em;
        color: white;
    }
    .hero p {
        margin: 1rem 0 0;
        max-width: 720px;
        color: #e4efe9;
        font-size: 1.04rem;
        line-height: 1.55;
    }
    .section-kicker {
        color: var(--juniper-700);
        font-weight: 800;
        font-size: .76rem;
        text-transform: uppercase;
        letter-spacing: .1em;
        margin-bottom: .15rem;
    }
    .section-copy { color: var(--muted); margin-top: -.35rem; }
    .workflow-card {
        min-height: 100%;
        padding: 1.15rem 1.2rem;
        border: 1px solid var(--line);
        border-radius: 16px;
        background: rgba(255,255,255,.72);
    }
    .workflow-card strong { color: var(--juniper-900); }
    .workflow-step {
        display: grid;
        grid-template-columns: 28px 1fr;
        gap: .65rem;
        align-items: start;
        margin: .7rem 0;
        color: var(--muted);
        font-size: .9rem;
    }
    .workflow-step span {
        display: grid;
        place-items: center;
        width: 26px;
        height: 26px;
        border-radius: 50%;
        background: #dce9e2;
        color: var(--juniper-900);
        font-weight: 800;
    }
    [data-testid="stMetric"] {
        background: rgba(255,255,255,.86);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 1rem 1.05rem;
        box-shadow: 0 6px 18px rgba(23,59,51,.05);
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--juniper-900); }
    [data-testid="stFileUploaderDropzone"] {
        background: rgba(255,255,255,.76);
        border: 1.5px dashed #8eaa9d;
        border-radius: 16px;
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    .stButton > button[kind="primary"] {
        min-height: 3.15rem;
        border-radius: 12px;
        border: 0;
        font-weight: 750;
        background: var(--juniper-700);
        box-shadow: 0 8px 20px rgba(40,94,79,.18);
    }
    .stButton > button[kind="primary"]:hover { background: var(--juniper-900); }
    [data-testid="stTabs"] [role="tablist"] { gap: .4rem; }
    [data-testid="stTabs"] button[role="tab"] {
        border-radius: 10px 10px 0 0;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    .result-note {
        border-left: 4px solid var(--juniper-500);
        background: #eef6f1;
        border-radius: 8px;
        padding: .8rem 1rem;
        margin: .5rem 0 1rem;
        color: var(--juniper-900);
    }
    .privacy-note {
        padding: .8rem .9rem;
        border-radius: 12px;
        background: rgba(255,255,255,.62);
        color: #53665f;
        font-size: .82rem;
        line-height: 1.45;
        border: 1px solid #dce5df;
    }
    @media (max-width: 700px) {
        .block-container { padding: 1rem .85rem 3rem; }
        .hero { padding: 1.45rem 1.25rem; border-radius: 18px; }
        .hero h1 { font-size: 2rem; }
        .hero p { font-size: .92rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Paramètres d'analyse")
    provider_label = st.selectbox(
        "Moteur sémantique",
        ["Démonstration hors ligne", "OpenRouter", "Anthropic"],
        help="Le mode hors ligne est immédiat et ne consomme aucun crédit API.",
    )
    provider = {
        "Démonstration hors ligne": "Offline demo",
        "OpenRouter": "OpenRouter",
        "Anthropic": "Anthropic",
    }[provider_label]

    model = "Deterministic keyword rules"
    api_key = ""
    if provider != "Offline demo":
        if provider == "Anthropic":
            model = st.selectbox(
                "Modèle Claude",
                options=list(ANTHROPIC_MODELS),
                format_func=lambda model_id: ANTHROPIC_MODELS[model_id],
                key="model_Anthropic",
                help="Haiku convient bien à la classification et au briefing court. Les modèles plus puissants peuvent coûter davantage.",
            )
        else:
            model = st.text_input(
                "Modèle OpenRouter",
                value="openai/gpt-4o-mini",
                key="model_OpenRouter",
            )
        secret_name = "OPENROUTER_API_KEY" if provider == "OpenRouter" else "ANTHROPIC_API_KEY"
        api_key = st.text_input(
            "Clé API",
            value=get_secret(secret_name),
            type="password",
            key=f"api_key_{provider}",
            help="La clé reste dans cette session Streamlit et n'est jamais écrite par l'application.",
        )

    language_label = st.selectbox("Langue du briefing", ["English", "Français"])
    language = "French" if language_label == "Français" else "English"
    st.markdown(
        """
        <div class="privacy-note">
        <strong>Contrôle humain requis.</strong><br>
        Le manager relit les étiquettes, ouvre les preuves et décide de toute action.
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <section class="hero">
      <div class="hero__topline"><span class="hero__dot"></span>Aide à la décision · Brief hebdomadaire</div>
      <h1>Du commentaire client à une décision traçable.</h1>
      <p>Une visite compte une fois. Les doublons sont fusionnés avant les calculs et chaque constat reste relié aux identifiants d'origine.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([2.15, 1], gap="large")
with left:
    st.markdown('<div class="section-kicker">01 · Importer</div>', unsafe_allow_html=True)
    st.subheader("Lot de retours clients")
    st.markdown(
        '<p class="section-copy">Déposez un CSV ou utilisez directement le jeu Case 04 préchargé.</p>',
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader(
        "Fichier CSV",
        type=["csv"],
        label_visibility="collapsed",
        help="Colonnes attendues : feedback_id, visit_id, branch, comment.",
    )
    file_col, template_col = st.columns([1.65, 1])
    with file_col:
        if uploaded is None:
            st.caption("Jeu actif : Case 04 · données fictives · 12 messages")
        else:
            st.caption(f"Jeu actif : {uploaded.name}")
    with template_col:
        st.download_button(
            "Télécharger le modèle CSV",
            STARTER.read_bytes(),
            file_name="juniper_feedback_template.csv",
            mime="text/csv",
            **STRETCH,
        )

with right:
    st.markdown(
        """
        <div class="workflow-card">
          <strong>Ce que fait le pipeline</strong>
          <div class="workflow-step"><span>1</span><div>Valide le fichier et regroupe les messages par visite.</div></div>
          <div class="workflow-step"><span>2</span><div>Étiquette les thèmes et les avis mixtes.</div></div>
          <div class="workflow-step"><span>3</span><div>Calcule les ratios exacts et vérifie les preuves.</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

source = uploaded if uploaded is not None else str(STARTER)
try:
    messages = load_feedback(source)
    dedupe = deduplicate_visits(messages)
except InputValidationError as exc:
    st.error(f"Impossible d'utiliser ce fichier : {exc}", icon="⚠️")
    st.info("Corrigez le CSV puis importez-le à nouveau. Le modèle téléchargeable contient les bonnes colonnes.")
    st.stop()

current_fingerprint = batch_fingerprint(messages)
if "result" in st.session_state and st.session_state["result"].get("batch_hash") != current_fingerprint:
    del st.session_state["result"]
    st.toast("Le lot a changé : l'ancien briefing a été retiré.", icon="↻")

st.divider()
st.markdown('<div class="section-kicker">02 · Contrôler</div>', unsafe_allow_html=True)
st.subheader("Unité d'observation : la visite")

metric_1, metric_2, metric_3 = st.columns(3)
metric_1.metric("Messages reçus", len(messages))
metric_2.metric("Visites uniques", len(dedupe.visits))
metric_3.metric("Messages fusionnés", len(messages) - len(dedupe.visits))

with st.expander("Voir les données et l'audit de déduplication"):
    data_tab, audit_tab = st.tabs(["Messages d'origine", "Décisions de déduplication"])
    with data_tab:
        st.dataframe(messages, hide_index=True, **STRETCH)
    with audit_tab:
        st.dataframe(dedupe.audit, hide_index=True, **STRETCH)
        for warning in dedupe.warnings:
            st.warning(warning)

st.markdown('<div class="section-kicker" style="margin-top:1.1rem">03 · Générer</div>', unsafe_allow_html=True)
st.subheader("Briefing opérationnel")
action_col, assurance_col = st.columns([1.25, 1.75], vertical_alignment="center")
with action_col:
    generate = st.button("Générer le briefing", type="primary", **STRETCH)
with assurance_col:
    if provider == "Offline demo":
        st.caption("Mode démonstration : règles transparentes, aucun appel API.")
    else:
        st.caption(f"Mode {provider} : classification puis synthèse, avec validation déterministe et repli sécurisé.")

if generate:
    run_log = [
        {"level": "success", "message": f"{len(messages)} messages chargés et validés."},
        {
            "level": "success",
            "message": f"{len(dedupe.visits)} visites uniques après fusion des répétitions.",
        },
    ]
    client: LLMClient | None = None
    with st.spinner("Classification, calcul des ratios et préparation du briefing..."):
        if provider == "Offline demo":
            classifications = heuristic_classify(dedupe.visits)
            run_log.append(
                {"level": "info", "message": "Classification multi-label hors ligne appliquée."}
            )
        else:
            try:
                client = LLMClient(provider, api_key, model)
                classifications = client.classify(dedupe.visits)
                run_log.append(
                    {"level": "success", "message": f"Visites classifiées avec {provider} · {model}."}
                )
            except Exception as exc:
                classifications = heuristic_classify(dedupe.visits)
                run_log.append(
                    {
                        "level": "warning",
                        "message": f"Classification API indisponible ; repli hors ligne utilisé. Détail : {exc}",
                    }
                )

        aggregates = compute_aggregates(dedupe.visits, classifications, len(messages))
        run_log.append(
            {"level": "success", "message": "Ratios et répartitions calculés en Python sur les visites uniques."}
        )
        briefing = build_deterministic_briefing(aggregates, language)

        if client is not None:
            try:
                candidate = client.synthesize(aggregates, language)
                validation_errors = validate_briefing(candidate, aggregates)
                if validation_errors:
                    run_log.append(
                        {
                            "level": "warning",
                            "message": "Le brouillon LLM n'a pas passé les contrôles ; briefing déterministe utilisé. "
                            + " | ".join(validation_errors),
                        }
                    )
                else:
                    briefing = candidate
                    run_log.append(
                        {"level": "success", "message": "Brouillon LLM accepté après validation déterministe."}
                    )
            except Exception as exc:
                run_log.append(
                    {
                        "level": "warning",
                        "message": f"Synthèse API indisponible ; briefing déterministe utilisé. Détail : {exc}",
                    }
                )

        st.session_state["result"] = {
            "batch_hash": current_fingerprint,
            "briefing": briefing,
            "pdf": briefing_to_pdf(briefing),
            "classifications": classifications,
            "visits": dedupe.visits.copy(),
            "aggregates": aggregates,
            "run_log": run_log,
        }

if "result" in st.session_state:
    result = st.session_state["result"]
    st.markdown(
        '<div class="result-note"><strong>Briefing prêt.</strong> Les nombres sont calculés sur les visites uniques et les références ont été contrôlées.</div>',
        unsafe_allow_html=True,
    )
    brief_tab, evidence_tab, trace_tab = st.tabs(["Briefing", "Preuves", "Traçabilité"])

    with brief_tab:
        with st.container(border=True):
            st.markdown(result["briefing"])
        markdown_col, pdf_col = st.columns(2)
        markdown_col.download_button(
            "Télécharger en Markdown",
            result["briefing"].encode("utf-8"),
            file_name="juniper_operations_briefing.md",
            mime="text/markdown",
            **STRETCH,
        )
        pdf_col.download_button(
            "Télécharger en PDF",
            result["pdf"],
            file_name="juniper_operations_briefing.pdf",
            mime="application/pdf",
            **STRETCH,
        )

    with evidence_tab:
        st.markdown("#### Synthèse des thèmes")
        theme_rows = [
            {
                "Thème": item["theme"],
                "Fréquence": f"{item['visits']}/{item['denominator']}",
                "Références": ", ".join(f"[{ref}]" for ref in item["evidence"]),
            }
            for item in result["aggregates"]["themes"]
        ]
        st.dataframe(pd.DataFrame(theme_rows), hide_index=True, **STRETCH)

        st.markdown("#### Visites et commentaires sources")
        classification_view = result["visits"][
            ["visit_id", "primary_feedback_id", "source_feedback_ids", "branch", "comment"]
        ].merge(result["classifications"], on="visit_id", validate="one_to_one")
        classification_view["source_feedback_ids"] = classification_view["source_feedback_ids"].map(
            lambda ids: ", ".join(ids)
        )
        classification_view["themes"] = classification_view["themes"].map(lambda values: " · ".join(values))
        classification_view = classification_view.rename(
            columns={
                "visit_id": "Visite",
                "primary_feedback_id": "ID principal",
                "source_feedback_ids": "IDs sources",
                "branch": "Établissement",
                "comment": "Commentaire",
                "themes": "Thèmes",
                "sentiment": "Tonalité",
                "rationale": "Justification",
            }
        )
        st.dataframe(classification_view, hide_index=True, **STRETCH)
        st.caption("Un même commentaire peut appartenir à plusieurs thèmes ; les fréquences ne s'additionnent donc pas à 100 %.")

    with trace_tab:
        st.markdown("#### Journal du pipeline")
        for item in result["run_log"]:
            if item["level"] == "success":
                st.success(item["message"], icon="✅")
            elif item["level"] == "warning":
                st.warning(item["message"], icon="⚠️")
            else:
                st.info(item["message"], icon="ℹ️")
        with st.expander("Voir les agrégats techniques"):
            st.json(result["aggregates"], expanded=False)
