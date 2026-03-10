"""Generování PDF dodacího listu (reportlab) s podporou české diakritiky."""
import os
from io import BytesIO
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from app.models import DeliveryNote

# Font s českou diakritikou – první dostupný se použije
_CZECH_FONT_PATHS = [
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arial.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
_CZECH_FONT_NAME = None


def _get_czech_font():
    global _CZECH_FONT_NAME
    if _CZECH_FONT_NAME:
        return _CZECH_FONT_NAME
    for path in _CZECH_FONT_PATHS:
        if path and os.path.isfile(path):
            try:
                name = "CzechFont"
                pdfmetrics.registerFont(TTFont(name, path))
                _CZECH_FONT_NAME = name
                return name
            except Exception:
                continue
    return "Helvetica"


def _decimal_str(d: Decimal | None) -> str:
    if d is None:
        return ""
    return str(d)


def generate_delivery_note_pdf(note: DeliveryNote) -> bytes:
    """Vygeneruje PDF dodacího listu do bytes."""
    font_name = _get_czech_font()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=14,
        fontName=font_name,
    )
    normal_style = ParagraphStyle("NormalCzech", parent=styles["Normal"], fontName=font_name)

    story = []
    story.append(Paragraph("DODACÍ LIST", title_style))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"<b>Číslo dokladu:</b> {note.document_number}", normal_style))
    story.append(Paragraph(f"<b>Datum vystavení:</b> {note.issue_date}", normal_style))
    story.append(Paragraph(f"<b>Datum dodání:</b> {note.delivery_date}", normal_style))
    story.append(Spacer(1, 4 * mm))

    c = note.customer
    story.append(Paragraph("<b>Odběratel</b>", normal_style))
    story.append(Paragraph((c.company_name or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), normal_style))
    addr = []
    if c.street:
        addr.append(c.street)
    if c.zip_code or c.city:
        addr.append(f"{c.zip_code or ''} {c.city or ''}".strip())
    if c.country:
        addr.append(c.country)
    if c.ico:
        addr.append(f"IČO: {c.ico}")
    if c.dic:
        addr.append(f"DIČ: {c.dic}")
    if addr:
        story.append(Paragraph("<br/>".join(a.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") for a in addr), normal_style))
    story.append(Spacer(1, 6 * mm))

    # Tabulka položek
    data = [["Položka", "Množství", "Jedn.", "Cena/jedn.", "Celkem"]]
    for item in note.items:
        data.append([
            item.item_name + (f" – {item.item_description}" if item.item_description else ""),
            _decimal_str(item.quantity),
            item.unit or "ks",
            _decimal_str(item.unit_price),
            _decimal_str(item.line_total),
        ])
    if note.note:
        data.append(["Poznámka:", note.note, "", "", ""])
    data.append(["", "", "", "Celkem:", _decimal_str(note.total_amount)])

    t = Table(data, colWidths=[70 * mm, 20 * mm, 20 * mm, 25 * mm, 30 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, -1), (-1, -1), font_name),
    ]))
    story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
