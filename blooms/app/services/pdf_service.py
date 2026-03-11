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

# Font s českou diakritikou – první dostupný se použije (Windows, Debian, Arch/CachyOS)
_CZECH_FONT_PATHS = [
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arial.ttf"),
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "Arial.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/LiberationSans-Regular.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/google-noto-fonts/NotoSans-Regular.ttf",
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


def _esc(text: str | None) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _czech_date(d) -> str:
    """Formát data pro češtinu: 10. 3. 2026."""
    if d is None:
        return ""
    return f"{d.day}. {d.month}. {d.year}"


def generate_delivery_note_pdf(note: DeliveryNote, company_profile: dict | None = None) -> bytes:
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
        fontSize=11,
        fontName=font_name,
        textColor=colors.HexColor("#1f4330"),
        spaceAfter=1 * mm,
    )
    normal_style = ParagraphStyle("NormalCzech", parent=styles["Normal"], fontName=font_name, leading=10)
    label_style = ParagraphStyle(
        "Label",
        parent=normal_style,
        textColor=colors.HexColor("#4b6256"),
        fontSize=7,
        leading=9,
    )
    item_style = ParagraphStyle(
        "ItemName",
        parent=normal_style,
        fontSize=7,
        leading=8,
    )

    story = []
    cp = company_profile or {}
    # Layout jako tisk: vlevo firma + číslo DL, vpravo meta box
    company_block = []
    if cp.get("name"):
        company_block.append(Paragraph(_esc(cp.get("name")), title_style))
    if cp.get("street") or cp.get("city") or cp.get("zip") or cp.get("country") or cp.get("ico") or cp.get("dic"):
        addr_parts = []
        if cp.get("street"):
            addr_parts.append(cp.get("street"))
        if cp.get("zip") or cp.get("city"):
            addr_parts.append(f"{cp.get('zip') or ''} {cp.get('city') or ''}".strip())
        if cp.get("country"):
            addr_parts.append(cp.get("country"))
        if cp.get("ico"):
            addr_parts.append(f"IČO: {cp.get('ico')}")
        if cp.get("dic"):
            addr_parts.append(f"DIČ: {cp.get('dic')}")
        company_block.append(Paragraph("<br/>".join(_esc(x) for x in addr_parts if x), normal_style))
    if not company_block:
        company_block.append(Paragraph("Dodavatel", title_style))
    company_block.append(Paragraph("Číslo dodacího listu", label_style))
    company_block.append(Paragraph(f"<b>{_esc(note.document_number)}</b>", normal_style))
    left_data = [[p] for p in company_block]
    left_box = Table(left_data, colWidths=[100 * mm])
    left_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafcfb")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c8d7cf")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
    ]))

    meta_rows = [
        [Paragraph("Datum vystavení", label_style), Paragraph(_esc(_czech_date(note.issue_date)), normal_style)],
        [Paragraph("Datum dodání", label_style), Paragraph(_esc(_czech_date(note.delivery_date)), normal_style)],
        [Paragraph("Status", label_style), Paragraph("Vystaveno" if note.status == "issued" else "Koncept", normal_style)],
        [Paragraph("Celkem", label_style), Paragraph(f"<b>{_esc(_decimal_str(note.total_amount))}</b>", normal_style)],
    ]
    right_box = Table(meta_rows, colWidths=[42 * mm, 38 * mm])
    right_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c8d7cf")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2ebe5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
    ]))

    top = Table([[left_box, right_box]], colWidths=[100 * mm, 80 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(top)
    story.append(Spacer(1, 4 * mm))

    # Odběratel – box na celou šířku jako v tisku
    c = note.customer
    customer_lines = []
    if c.street:
        customer_lines.append(c.street)
    if c.zip_code or c.city:
        customer_lines.append(f"{c.zip_code or ''} {c.city or ''}".strip())
    if c.country:
        customer_lines.append(c.country)
    if c.ico:
        customer_lines.append(f"IČO: {c.ico}")
    if c.dic:
        customer_lines.append(f"DIČ: {c.dic}")
    cust_data = [
        [Paragraph("Odběratel", label_style)],
        [Paragraph(f"<b>{_esc(c.company_name or '')}</b>", normal_style)],
        [Paragraph("<br/>".join(_esc(x) for x in customer_lines), normal_style)],
    ]
    cust_box = Table(cust_data, colWidths=[180 * mm])
    cust_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f6faf7")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c8d7cf")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
    ]))
    story.append(cust_box)
    story.append(Spacer(1, 4 * mm))

    # Tabulka položek
    data = [["Položka", "Množství", "Jedn.", "Cena/jedn.", "Celkem"]]
    items_sorted = sorted(note.items, key=lambda i: ((i.item_name or "").casefold(), i.id or 0))
    for item in items_sorted:
        # Paragraph sám zalamuje text v rámci sloupce – zabrání přetékání do Množství/Jedn.
        name = _esc(item.item_name or "") + (_esc(f" – {item.item_description}") if item.item_description else "")
        data.append([
            Paragraph(name, item_style),
            _decimal_str(item.quantity),
            item.unit or "ks",
            _decimal_str(item.unit_price),
            _decimal_str(item.line_total),
        ])
    if note.note:
        data.append(["Poznámka:", _esc(note.note), "", "", ""])
    data.append(["", "", "", "Celkem:", _decimal_str(note.total_amount)])

    t = Table(data, colWidths=[75 * mm, 22 * mm, 18 * mm, 28 * mm, 32 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf3ee")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#244633")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#fbfdfc")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c8d7cf")),
        ("FONTNAME", (0, -1), (-1, -1), font_name),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f4f8f5")),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#1f4330")),
    ]))
    story.append(t)

    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Vygenerováno v systému Blooms", label_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
