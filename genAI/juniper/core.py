from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import BinaryIO, Iterable, TextIO

import pandas as pd


THEMES = (
    "Speed and queues",
    "Service and friendliness",
    "Cleanliness and seating",
    "Pricing and payment",
    "Availability and dietary options",
    "Order-ahead and collection",
    "Receipts",
    "Product quality and ambience",
    "Unclear or little usable detail",
)

SENTIMENTS = ("positive", "negative", "mixed", "neutral")


class InputValidationError(ValueError):
    """Raised when an uploaded batch cannot be safely interpreted."""


@dataclass(frozen=True)
class DeduplicationResult:
    visits: pd.DataFrame
    audit: pd.DataFrame
    warnings: tuple[str, ...]


_ALIASES = {
    "feedback_id": {"feedback_id", "feedback id", "id", "comment_id", "comment id"},
    "visit_id": {"visit_id", "visit id", "visit"},
    "branch": {"branch", "location", "site"},
    "comment": {"comment", "feedback", "message", "text"},
}
_COMBINED_ID_ALIASES = {"id / visit", "id/visit", "feedback / visit", "feedback/visit"}


def _normalise_header(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower().replace("_", " "))


def load_feedback(source: str | BinaryIO | TextIO | io.BytesIO) -> pd.DataFrame:
    """Read and validate a feedback CSV, accepting a few manager-friendly headers."""
    try:
        raw = pd.read_csv(source, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as exc:
        raise InputValidationError("The CSV is empty.") from exc
    except Exception as exc:
        raise InputValidationError(f"The CSV could not be read: {exc}") from exc

    if raw.empty:
        raise InputValidationError("The batch has headers but no feedback rows.")

    header_lookup = {_normalise_header(column): column for column in raw.columns}
    rename: dict[str, str] = {}
    for target, aliases in _ALIASES.items():
        for alias in aliases:
            normalised_alias = _normalise_header(alias)
            if normalised_alias in header_lookup:
                rename[header_lookup[normalised_alias]] = target
                break

    combined_column = next(
        (header_lookup[name] for name in _COMBINED_ID_ALIASES if name in header_lookup),
        None,
    )
    data = raw.rename(columns=rename).copy()
    if combined_column and not {"feedback_id", "visit_id"}.issubset(data.columns):
        parts = raw[combined_column].astype(str).str.split("/", n=1, expand=True)
        if parts.shape[1] != 2:
            raise InputValidationError(
                "The combined ID / visit column must look like 'F01 / V01'."
            )
        data["feedback_id"] = parts[0]
        data["visit_id"] = parts[1]

    required = ["feedback_id", "visit_id", "branch", "comment"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise InputValidationError(
            "Missing required column(s): " + ", ".join(missing) + "."
        )

    data = data[required].copy()
    for column in required:
        data[column] = data[column].astype(str).str.strip()
    blank_rows = data.index[(data[required] == "").any(axis=1)].tolist()
    if blank_rows:
        display_rows = ", ".join(str(index + 2) for index in blank_rows[:8])
        raise InputValidationError(
            f"Blank required value(s) found on CSV row(s): {display_rows}."
        )

    if data["feedback_id"].duplicated().any():
        repeated = sorted(data.loc[data["feedback_id"].duplicated(False), "feedback_id"].unique())
        raise InputValidationError(
            "Feedback IDs must be unique; repeated ID(s): " + ", ".join(repeated) + "."
        )
    return data.reset_index(drop=True)


def deduplicate_visits(messages: pd.DataFrame) -> DeduplicationResult:
    """Collapse messages to one observation per visit while retaining every source ID."""
    if messages.empty:
        raise InputValidationError("The batch contains no feedback rows.")

    visit_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    warnings: list[str] = []

    for visit_id, group in messages.groupby("visit_id", sort=False):
        group = group.reset_index(drop=True)
        source_ids = group["feedback_id"].tolist()
        branches = list(dict.fromkeys(group["branch"].tolist()))
        comments = list(dict.fromkeys(group["comment"].tolist()))
        if len(branches) > 1:
            warnings.append(
                f"Visit {visit_id} names multiple branches ({', '.join(branches)}); "
                f"the first value, {branches[0]}, is used for branch counts."
            )

        merged_comment = comments[0]
        if len(comments) > 1:
            merged_comment = "\n".join(
                f"[{row.feedback_id}] {row.comment}" for row in group.itertuples()
            )

        visit_rows.append(
            {
                "visit_id": visit_id,
                "primary_feedback_id": source_ids[0],
                "source_feedback_ids": tuple(source_ids),
                "branch": branches[0],
                "comment": merged_comment,
                "message_count": len(group),
            }
        )
        audit_rows.append(
            {
                "visit_id": visit_id,
                "retained_observation": f"{source_ids[0]}/{visit_id}",
                "source_feedback_ids": ", ".join(source_ids),
                "messages": len(group),
                "decision": (
                    "Merged repeated visit" if len(group) > 1 else "Kept as unique visit"
                ),
            }
        )

    return DeduplicationResult(
        visits=pd.DataFrame(visit_rows),
        audit=pd.DataFrame(audit_rows),
        warnings=tuple(warnings),
    )


def _contains(text: str, words: Iterable[str]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def heuristic_classify(visits: pd.DataFrame) -> pd.DataFrame:
    """Transparent offline classifier used for demonstrations and graceful fallback."""
    rows: list[dict[str, object]] = []
    for row in visits.itertuples():
        text = row.comment.lower()
        themes: list[str] = []
        if _contains(text, ("queue", "queued", "waited", "waiting", "quick", "rush", "minutes")):
            themes.append("Speed and queues")
        if _contains(text, ("friendly", "service", "staff", "team", "corrected")):
            themes.append("Service and friendliness")
        if _contains(text, ("clean", "table", "seat", "seats")):
            themes.append("Cleanliness and seating")
        if _contains(text, ("price", "paid", "payment", "board")):
            themes.append("Pricing and payment")
        if _contains(text, ("sold out", "oat", "vegan", "available", "availability", "pastry")):
            themes.append("Availability and dietary options")
        if _contains(text, ("ordered ahead", "order ahead", "collect", "collection", "pickup")):
            themes.append("Order-ahead and collection")
        if _contains(text, ("receipt", "receipts")):
            themes.append("Receipts")
        if _contains(text, ("coffee", "quiet", "corner", "read", "lovely", "great")):
            themes.append("Product quality and ambience")
        if not themes:
            themes.append("Unclear or little usable detail")

        positive = _contains(
            text, ("lovely", "friendly", "quiet", "good", "like", "quick", "great", "corrected")
        )
        negative = _contains(
            text,
            (
                "but",
                "could not",
                "sold out",
                "differed",
                "waited",
                "queue",
                "queued",
                "missed",
                "disappointing",
                "had to",
            ),
        )
        sentiment = "mixed" if positive and negative else "positive" if positive else "negative" if negative else "neutral"
        rows.append(
            {
                "visit_id": row.visit_id,
                "themes": themes,
                "sentiment": sentiment,
                "rationale": "Offline keyword rules; review before operational use.",
            }
        )
    return pd.DataFrame(rows)


def validate_classifications(visits: pd.DataFrame, classifications: pd.DataFrame) -> pd.DataFrame:
    required = {"visit_id", "themes", "sentiment", "rationale"}
    if not required.issubset(classifications.columns):
        raise ValueError("Classification output is missing required fields.")
    expected = set(visits["visit_id"])
    actual = set(classifications["visit_id"])
    if actual != expected or len(classifications) != len(visits):
        raise ValueError("Classification output must contain exactly one row per unique visit.")
    cleaned = classifications.copy()
    for index, row in cleaned.iterrows():
        themes = row["themes"]
        if not isinstance(themes, list) or not themes:
            raise ValueError(f"Visit {row['visit_id']} has no theme list.")
        unknown = set(themes) - set(THEMES)
        if unknown:
            raise ValueError(f"Unknown themes for visit {row['visit_id']}: {sorted(unknown)}")
        if row["sentiment"] not in SENTIMENTS:
            raise ValueError(f"Unknown sentiment for visit {row['visit_id']}.")
        cleaned.at[index, "themes"] = list(dict.fromkeys(themes))
    return cleaned


def evidence_label(visit_row: pd.Series | object) -> str:
    ids = list(visit_row.source_feedback_ids)
    visit_id = visit_row.visit_id
    return "/".join(ids + [visit_id])


def compute_aggregates(visits: pd.DataFrame, classifications: pd.DataFrame, total_messages: int) -> dict:
    """Compute all reportable counts deterministically at the unique-visit level."""
    classifications = validate_classifications(visits, classifications)
    merged = visits.merge(classifications, on="visit_id", validate="one_to_one")
    total = len(merged)

    themes: list[dict[str, object]] = []
    for theme in THEMES:
        selected = merged[merged["themes"].map(lambda values: theme in values)]
        if selected.empty:
            continue
        themes.append(
            {
                "theme": theme,
                "visits": len(selected),
                "denominator": total,
                "evidence": [evidence_label(row) for row in selected.itertuples()],
                "visit_ids": selected["visit_id"].tolist(),
            }
        )
    themes.sort(key=lambda item: (-int(item["visits"]), THEMES.index(str(item["theme"]))))

    branches: list[dict[str, object]] = []
    for branch, selected in merged.groupby("branch", sort=True):
        branches.append(
            {
                "branch": branch,
                "visits": len(selected),
                "denominator": total,
                "evidence": [evidence_label(row) for row in selected.itertuples()],
            }
        )

    sentiments = {
        sentiment: int((merged["sentiment"] == sentiment).sum()) for sentiment in SENTIMENTS
    }
    catalog = [
        {
            "reference": evidence_label(row),
            "visit_id": row.visit_id,
            "branch": row.branch,
            "comment": row.comment,
            "themes": row.themes,
            "sentiment": row.sentiment,
        }
        for row in merged.itertuples()
    ]
    return {
        "total_messages": int(total_messages),
        "total_unique_visits": total,
        "duplicates_removed": int(total_messages - total),
        "themes": themes,
        "branches": branches,
        "sentiments": sentiments,
        "evidence_catalog": catalog,
    }

