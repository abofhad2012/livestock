# reports/pdf_summary.py
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Iterable

from django.conf import settings
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


_AR_RE = re.compile(r"[\u0600-\u06FF]")


def _rtl(text: str) -> str:
    """
    RTL shaping إذا توفر arabic_reshaper + python-bidi.
    إذا غير متوفرين، يرجع النص كما هو.
    """
    if not text:
        return ""
    if not _AR_RE.search(text):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def _fmt_money(x, places: int = 2) -> str:
    """
    42200 -> 42,200.00
    """
    try:
        d = Decimal(str(x or 0))
    except Exception:
        d = Decimal("0")

    q = Decimal("1") if places == 0 else Decimal("0." + ("0" * (places - 1)) + "1")
    d = d.quantize(q)
    return f"{d:,.{places}f}"


def _register_fonts() -> tuple[str, str]:
    """
    ضع الخطين في:
      static/fonts/Cairo-Regular.ttf
      static/fonts/Cairo-Bold.ttf
    """
    reg = os.path.join(settings.BASE_DIR, "static", "fonts", "Cairo-Regular.ttf")
    bold = os.path.join(settings.BASE_DIR, "static", "fonts", "Cairo-Bold.ttf")

    # fallback
    font = "Helvetica"
    font_b = "Helvetica-Bold"

    if os.path.exists(reg):
        pdfmetrics.registerFont(TTFont("Cairo", reg))
        font = "Cairo"
    if os.path.exists(bold):
        pdfmetrics.registerFont(TTFont("CairoBold", bold))
        font_b = "CairoBold"

    return font, font_b


@dataclass
class SummaryTotals:
    sales: Decimal
    purchases: Decimal
    paid: Decimal
    due: Decimal


@dataclass
class BreakdownRow:
    tx_type_label: str
    kind_label: str
    class_label: str
    qty: Decimal
    total: Decimal


@dataclass
class TxRow:
    tx_date: date
    tx_type_label: str
    reference: str
    total: Decimal
    paid: Decimal
    due: Decimal
    customer: str


def render_summary_pdf(
    *,
    farm_name: str,
    date_from: date,
    date_to: date,
    totals: SummaryTotals,
    breakdown: Iterable[BreakdownRow],
    recent: Iterable[TxRow],
) -> bytes:
    font, font_b = _register_fonts()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
        title="تقرير ملخص (تقارير ذكية)",
        author=farm_name or "محاسبة المواشي",
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "T",
        parent=styles["Title"],
        fontName=font_b,
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
    )
    sub = ParagraphStyle(
        "S",
        parent=styles["Normal"],
        fontName=font,
        fontSize=10.5,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#334155"),
    )
    h = ParagraphStyle(
        "H",
        parent=styles["Heading3"],
        fontName=font_b,
        fontSize=12.5,
        leading=16,
        alignment=TA_RIGHT,
        spaceBefore=6,
        spaceAfter=4,
    )
    p = ParagraphStyle(
        "P",
        parent=styles["Normal"],
        fontName=font,
        fontSize=10.5,
        leading=14,
        alignment=TA_RIGHT,
    )

    def on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont(font, 9)
        ts = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M")
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, _rtl(f"{farm_name} — تم إنشاء التقرير: {ts}"))
        canvas.drawString(16 * mm, 9 * mm, str(_doc.page))
        canvas.restoreState()

    story = []

    story.append(Paragraph(_rtl("تقرير ملخص (تقارير ذكية)"), title))
    story.append(Paragraph(_rtl(farm_name or "محاسبة المواشي"), sub))
    story.append(Paragraph(_rtl(f"الفترة: {date_from} → {date_to}"), sub))
    story.append(Spacer(1, 6 * mm))

    # Summary table
    story.append(Paragraph(_rtl("الملخص المالي"), h))
    summary_data = [
        [_rtl("إجمالي المبيعات"), _fmt_money(totals.sales)],
        [_rtl("إجمالي المشتريات"), _fmt_money(totals.purchases)],
        [_rtl("إجمالي المدفوع"), _fmt_money(totals.paid)],
        [_rtl("إجمالي الآجل"), _fmt_money(totals.due)],
    ]
    t = Table(summary_data, colWidths=[75 * mm, 60 * mm])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("FONTNAME", (0, 0), (0, -1), font_b),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.whitesmoke, colors.HexColor("#F8FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    # Breakdown table
    story.append(Paragraph(_rtl("تفصيل النوع/الصنف (حسب البنود)"), h))
    breakdown = list(breakdown)
    if not breakdown:
        story.append(Paragraph(_rtl("لا توجد بيانات ضمن الفترة المحددة."), p))
    else:
        b_data = [[_rtl("الحركة"), _rtl("النوع"), _rtl("الصنف"), _rtl("الكمية"), _rtl("الإجمالي (ريال)")]]
        for r in breakdown:
            b_data.append(
                [
                    _rtl(r.tx_type_label),
                    _rtl(r.kind_label),
                    _rtl(r.class_label or "—"),
                    str(r.qty),
                    _fmt_money(r.total),
                ]
            )
        bt = Table(b_data, colWidths=[18 * mm, 40 * mm, 30 * mm, 25 * mm, 45 * mm])
        bt.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), font_b),
                    ("FONTNAME", (0, 1), (-1, -1), font),
                    ("FONTSIZE", (0, 0), (-1, -1), 10.5),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1733")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("ALIGN", (0, 1), (2, -1), "RIGHT"),
                    ("ALIGN", (3, 1), (4, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(bt)

    story.append(Spacer(1, 6 * mm))

    # Recent transactions
    story.append(Paragraph(_rtl("آخر العمليات"), h))
    recent = list(recent)
    if not recent:
        story.append(Paragraph(_rtl("لا توجد عمليات ضمن الفترة المحددة."), p))
    else:
        r_data = [[_rtl("التاريخ"), _rtl("النوع"), _rtl("المرجع"), _rtl("الإجمالي"), _rtl("مدفوع"), _rtl("آجل"), _rtl("العميل")]]
        for tx in recent[:15]:
            r_data.append(
                [
                    str(tx.tx_date),
                    _rtl(tx.tx_type_label),
                    _rtl(tx.reference),
                    _fmt_money(tx.total),
                    _fmt_money(tx.paid),
                    _fmt_money(tx.due),
                    _rtl(tx.customer or "—"),
                ]
            )

        rt = Table(r_data, colWidths=[20 * mm, 18 * mm, 30 * mm, 22 * mm, 20 * mm, 20 * mm, 35 * mm])
        rt.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), font_b),
                    ("FONTNAME", (0, 1), (-1, -1), font),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1733")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("ALIGN", (0, 1), (2, -1), "RIGHT"),
                    ("ALIGN", (3, 1), (5, -1), "LEFT"),
                    ("ALIGN", (6, 1), (6, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(rt)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()