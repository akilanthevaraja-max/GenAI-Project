from __future__ import annotations

import html
import io
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


NAVY = colors.HexColor("#123047")
GREEN = colors.HexColor("#4E7A63")
CREAM = colors.HexColor("#F7F3EA")
SLATE = colors.HexColor("#425466")


def _inline(text: str) -> str:
    escaped = html.escape(text.strip())
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", escaped)
    return escaped


def briefing_to_pdf(markdown: str, title: str = "Juniper Cafe operations briefing") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=19 * mm,
        bottomMargin=17 * mm,
        title=title,
        author="Juniper Cafe briefing app",
    )
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "JuniperTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=NAVY,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "JuniperH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=GREEN,
            spaceBefore=10,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "JuniperBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=SLATE,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "JuniperBullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.25,
            leading=13,
            textColor=SLATE,
            leftIndent=10,
            firstLineIndent=-7,
            bulletIndent=0,
            spaceAfter=4,
        ),
    }

    story = [
        Paragraph("JUNIPER CAFE", ParagraphStyle("Kicker", parent=styles["body"], fontSize=8, textColor=GREEN, leading=10)),
        Spacer(1, 2 * mm),
    ]
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 2 * mm))
        elif stripped.startswith("# "):
            story.append(Paragraph(_inline(stripped[2:]), styles["title"]))
        elif stripped.startswith("## "):
            if stripped.startswith("## Recommended investigation") or stripped.startswith(
                "## Investigation recommandee"
            ):
                story.append(PageBreak())
            story.append(Paragraph(_inline(stripped[3:]), styles["h2"]))
        elif stripped.startswith("- "):
            story.append(Paragraph(_inline(stripped[2:]), styles["bullet"], bulletText="-"))
        elif stripped == "---":
            story.append(PageBreak())
        else:
            story.append(Paragraph(_inline(stripped), styles["body"]))

    def decorate(canvas, document):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(CREAM)
        canvas.rect(0, height - 8 * mm, width, 8 * mm, fill=1, stroke=0)
        canvas.setStrokeColor(GREEN)
        canvas.setLineWidth(0.6)
        canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
        canvas.setFillColor(SLATE)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(18 * mm, 8.5 * mm, "Manager review required - generated from a convenience sample")
        canvas.drawRightString(width - 18 * mm, 8.5 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()
