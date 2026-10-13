from __future__ import annotations

import json
import re
from collections import Counter


def _refs(items: list[str]) -> str:
    return " ".join(f"[{item}]" for item in items)


def build_deterministic_briefing(aggregates: dict, language: str = "English") -> str:
    """Create a safe briefing when an LLM is unavailable or its output fails validation."""
    total = aggregates["total_unique_visits"]
    if language == "French":
        return _build_french(aggregates)

    lines = [
        "# Juniper Cafe - Weekly operations briefing",
        "",
        "## Scope and data quality",
        "",
        f"This batch contains **{aggregates['total_messages']} messages representing {total} unique visits**. "
        f"Python merged **{aggregates['duplicates_removed']} repeated message(s)** before any counts were calculated. "
        "The comments are a convenience sample: there is no complete customer count, sales volume, staffing record, "
        "or response-rate context, so the findings describe this batch only.",
        "",
        "## What the comments say",
        "",
    ]
    for item in aggregates["themes"]:
        lines.append(
            f"- **{item['theme']}: {item['visits']}/{total} visits.** "
            f"Evidence: {_refs(item['evidence'])}"
        )

    lines.extend(["", "## Branch context", ""])
    for item in aggregates["branches"]:
        lines.append(
            f"- **{item['branch']}: {item['visits']}/{total} visits in this batch.** "
            f"Evidence: {_refs(item['evidence'])}"
        )

    mixed = [
        item["reference"]
        for item in aggregates["evidence_catalog"]
        if item["sentiment"] == "mixed"
    ]
    unclear = next(
        (item for item in aggregates["themes"] if item["theme"] == "Unclear or little usable detail"),
        None,
    )
    lines.extend(["", "## Interpretation for manager review", ""])
    if mixed:
        lines.append(
            "- Mixed comments should not be flattened into one sentiment: several visits pair praise with a problem. "
            f"Evidence: {_refs(mixed)}"
        )
    if unclear:
        lines.append(
            "- One or more comments contain too little detail to support an operational diagnosis; they are retained "
            f"rather than guessed. Evidence: {_refs(unclear['evidence'])}"
        )
    top = aggregates["themes"][0] if aggregates["themes"] else None
    if top:
        lines.append(
            f"- **Interpretation, not a causal claim:** {top['theme']} is the most frequently tagged theme in this batch "
            f"({top['visits']}/{total}); this prioritises a question to investigate, not a conclusion about all customers. "
            f"Evidence: {_refs(top['evidence'])}"
        )

    speed = next((item for item in aggregates["themes"] if item["theme"] == "Speed and queues"), top)
    action_refs = speed["evidence"] if speed else [aggregates["evidence_catalog"][0]["reference"]]
    lines.extend(
        [
            "",
            "## Recommended investigation (exactly one)",
            "",
            "For one week, record **actual wait time from joining the queue or placing an order to hand-off**, "
            "in 30-minute intervals at each branch, separating walk-in and order-ahead visits. Compare the distribution "
            "with the wait-related comments, then let the manager decide whether a small process test is warranted. "
            f"Evidence motivating the investigation: {_refs(action_refs)}",
            "",
            "**Extra data required:** timestamped queue-entry/order and hand-off times, branch, channel (walk-in or "
            "order-ahead), 30-minute customer/order volume, scheduled staffing by role, and any unusual disruption. "
            "These data are needed to test timing and workload patterns; the comments alone do not establish a cause.",
            "",
            "## Human decision",
            "",
            "A manager should inspect the cited comments, confirm that the theme labels are reasonable, review the "
            "operational feasibility of the investigation, and decide whether to act.",
        ]
    )
    return "\n".join(lines)


def _build_french(aggregates: dict) -> str:
    total = aggregates["total_unique_visits"]
    lines = [
        "# Juniper Cafe - Brief operationnel hebdomadaire",
        "",
        "## Perimetre et qualite des donnees",
        "",
        f"Ce lot contient **{aggregates['total_messages']} messages representant {total} visites uniques**. "
        f"Python a fusionne **{aggregates['duplicates_removed']} message(s) repete(s)** avant tout calcul. "
        "Les commentaires constituent un echantillon de convenance, sans nombre complet de clients, volume de ventes, "
        "donnees de personnel ni taux de reponse. Les constats decrivent uniquement ce lot.",
        "",
        "## Ce que disent les commentaires",
        "",
    ]
    for item in aggregates["themes"]:
        lines.append(
            f"- **{item['theme']} : {item['visits']}/{total} visites.** Preuves : {_refs(item['evidence'])}"
        )
    lines.extend(["", "## Contexte par etablissement", ""])
    for item in aggregates["branches"]:
        lines.append(
            f"- **{item['branch']} : {item['visits']}/{total} visites dans ce lot.** "
            f"Preuves : {_refs(item['evidence'])}"
        )
    mixed = [x["reference"] for x in aggregates["evidence_catalog"] if x["sentiment"] == "mixed"]
    lines.extend(["", "## Interpretation soumise au manager", ""])
    if mixed:
        lines.append(
            "- Les avis mixtes ne doivent pas etre reduits a un sentiment unique : certaines visites associent un "
            f"compliment et un probleme. Preuves : {_refs(mixed)}"
        )
    top = aggregates["themes"][0]
    lines.append(
        f"- **Interpretation, et non causalite :** {top['theme']} est le theme le plus souvent etiquete dans ce lot "
        f"({top['visits']}/{total}). Cela priorise une question, sans decrire tous les clients. "
        f"Preuves : {_refs(top['evidence'])}"
    )
    speed = next((x for x in aggregates["themes"] if x["theme"] == "Speed and queues"), top)
    lines.extend(
        [
            "",
            "## Investigation recommandee (exactement une)",
            "",
            "Pendant une semaine, mesurer le **temps reel entre l'arrivee dans la file ou la commande et la remise**, "
            "par tranches de 30 minutes et par etablissement, en distinguant sur place et commande a l'avance. "
            f"Preuves motivant l'investigation : {_refs(speed['evidence'])}",
            "",
            "**Donnees supplementaires requises :** horodatage d'entree/commande et de remise, etablissement, canal, "
            "volume de commandes par tranche de 30 minutes, personnel planifie par role et perturbations inhabituelles. "
            "Les commentaires seuls ne permettent pas d'etablir une cause.",
            "",
            "## Decision humaine",
            "",
            "Le manager doit relire les commentaires cites, valider les etiquettes, verifier la faisabilite de "
            "l'investigation et decider de la suite.",
        ]
    )
    return "\n".join(lines)


def synthesis_prompt(aggregates: dict, language: str) -> tuple[str, str]:
    system = (
        "You write concise operations briefings. Treat every number in the supplied JSON as fixed. "
        "Do not calculate new counts, infer causes, or generalise beyond the batch. Return Markdown only."
    )
    investigation_heading = (
        "## Investigation recommandee (exactement une)"
        if language == "French"
        else "## Recommended investigation (exactly one)"
    )
    user = f"""Write the briefing in {language}. Follow every rule:
1. Use only ratios present in the JSON, formatted as Visits/Total Unique Visits.
2. Every operational finding or interpretation must end with one or more evidence references in square brackets.
3. Explicitly say this is a convenience sample without total customer or sales-volume context.
4. Separate observations from interpretation.
5. Include one section headed exactly '{investigation_heading}' and suggest exactly one small investigation.
6. State the extra data needed to test it.
7. Retain mixed/conflicting feedback and low-detail feedback.
8. End with the manager's human review responsibility.

Deterministic JSON:
{json.dumps(aggregates, ensure_ascii=False, indent=2)}
"""
    return system, user


def validate_briefing(markdown: str, aggregates: dict) -> list[str]:
    errors: list[str] = []
    investigation_sections = markdown.count(
        "## Recommended investigation (exactly one)"
    ) + markdown.count("## Investigation recommandee (exactement une)")
    if investigation_sections != 1:
        errors.append("The briefing must contain exactly one recommended-investigation section.")
    lower = markdown.lower()
    if "convenience sample" not in lower and "echantillon de convenance" not in lower:
        errors.append("The convenience-sample limitation is missing.")
    if not any(term in lower for term in ("extra data", "additional data", "donnees supplementaires")):
        errors.append("The extra data needed for the investigation are missing.")

    valid_refs = {item["reference"] for item in aggregates["evidence_catalog"]}
    found_refs = re.findall(r"\[([A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)+)\]", markdown)
    unknown = sorted(set(found_refs) - valid_refs)
    if unknown:
        errors.append("Unknown evidence reference(s): " + ", ".join(unknown))
    if not found_refs:
        errors.append("No evidence references were found.")

    allowed_ratios = {
        f"{item['visits']}/{item['denominator']}" for item in aggregates["themes"] + aggregates["branches"]
    }
    found_ratios = set(re.findall(r"(?<![A-Za-z0-9_/])(\d+/\d+)(?![A-Za-z0-9_/])", markdown))
    invalid_ratios = sorted(found_ratios - allowed_ratios)
    if invalid_ratios:
        errors.append("Unsupported ratio(s): " + ", ".join(invalid_ratios))

    # This flags accidental repeated recommendation headings while allowing evidence bullets elsewhere.
    heading_counts = Counter(re.findall(r"^##\s+(.+)$", markdown, flags=re.MULTILINE))
    if any(count > 1 for count in heading_counts.values()):
        errors.append("A section heading is repeated.")
    return errors
