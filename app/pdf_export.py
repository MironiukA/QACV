from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


FONT_NAME = "QACVArialUnicode"
FONT_PATH = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")


def create_resume_pdf(content: str) -> bytes:
    if not FONT_PATH.exists():
        raise RuntimeError("A Unicode font is required to export a Russian PDF")
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=19 * mm,
        rightMargin=19 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title="QACV Resume",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "ResumeTitle",
        parent=styles["Title"],
        fontName=FONT_NAME,
        fontSize=20,
        leading=25,
        textColor=HexColor("#172028"),
        alignment=TA_LEFT,
        spaceAfter=10,
    )
    heading = ParagraphStyle(
        "ResumeHeading",
        parent=styles["Heading2"],
        fontName=FONT_NAME,
        fontSize=13,
        leading=17,
        textColor=HexColor("#22485B"),
        spaceBefore=11,
        spaceAfter=5,
    )
    body = ParagraphStyle(
        "ResumeBody",
        parent=styles["BodyText"],
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        textColor=HexColor("#172028"),
        spaceAfter=4,
    )

    story = []
    for line in content.splitlines():
        text = line.strip()
        if not text:
            story.append(Spacer(1, 4))
        elif text.startswith("# "):
            story.append(Paragraph(escape(text[2:]), title))
        elif text.startswith("## "):
            story.append(Paragraph(escape(text[3:]), heading))
        elif text.startswith("- ") or text.startswith("* "):
            story.append(Paragraph(f"&bull; {escape(text[2:])}", body))
        else:
            story.append(Paragraph(escape(text), body))
    document.build(story or [Paragraph("Resume", title)])
    return buffer.getvalue()
