from __future__ import annotations

import re
from decimal import Decimal
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .pdf_fonts import register_arabic_fonts

try:
    import arabic_reshaper
except Exception:
    arabic_reshaper = None

try:
    from bidi import get_display as bidi_get_display
except Exception:
    try:
        from bidi.algorithm import get_display as bidi_get_display
    except Exception:
        bidi_get_display = None


_AR_RE = re.compile(r"[\u0600-\u06FF]")

_FONT_READY = False
_AR_FONT = "Helvetica"
_AR_FONT_B = "Helvetica-Bold"
_LATIN_FONT = "Helvetica"
_LATIN_FONT_B = "Helvetica-Bold"


def _has_arabic(text: Any) -> bool:
    s = "" if text is None else str(text)
    return bool(_AR_RE.search(s))


def _rtl(text: Any) -> str:
    s = "" if text is None else str(text)
    if not s or not _has_arabic(s):
        return s

    if arabic_reshaper is None or bidi_get_display is None:
        return s

    try:
        return bidi_get_display(arabic_reshaper.reshape(s))
    except Exception:
        return s


def _xml_text(text: Any, *, rtl: bool = False, auto: bool = False) -> str:
    s = "" if text is None else str(text)
    if rtl or (auto and _has_arabic(s)):
        s = _rtl(s)
    return escape(s).replace("\n", "<br/>")


def _p(text: Any, style: ParagraphStyle, *, rtl: bool = False, auto: bool = False) -> Paragraph:
    return Paragraph(_xml_text(text, rtl=rtl, auto=auto), style)


def _p_auto(text: Any, style_ar: ParagraphStyle, style_ltr: ParagraphStyle) -> Paragraph:
    s = "" if text is None else str(text)
    if _has_arabic(s):
        return Paragraph(_xml_text(s, rtl=True), style_ar)
    return Paragraph(_xml_text(s), style_ltr)


def _fmt_money(x: Any, places: int = 2) -> str:
    try:
        d = Decimal(str(x or 0))
    except Exception:
        d = Decimal("0")

    q = Decimal("1") if places == 0 else Decimal("0." + ("0" * (places - 1)) + "1")
    d = d.quantize(q)
    return f"{d:,.{places}f}"


def _ensure_fonts() -> tuple[str, str, str, str]:
    global _FONT_READY, _AR_FONT, _AR_FONT_B

    if _FONT_READY:
        return _AR_FONT, _AR_FONT_B, _LATIN_FONT, _LATIN_FONT_B

    try:
        register_arabic_fonts()
        _AR_FONT = "NotoNaskhArabic"
        _AR_FONT_B = "NotoNaskhArabic-Bold"
        _FONT_READY = True
    except Exception:
        _AR_FONT = "Helvetica"
        _AR_FONT_B = "Helvetica-Bold"

    return _AR_FONT, _AR_FONT_B, _LATIN_FONT, _LATIN_FONT_B


def _money_cell(x: Any) -> str:
    return _fmt_money(x)


def _canvas_text(text: Any) -> str:
    s = "" if text is None else str(text)
    return _rtl(s) if _has_arabic(s) else s


def _pick_canvas_font(text: Any, *, bold: bool = False) -> str:
    ar_font, ar_font_b, latin_font, latin_font_b = _ensure_fonts()
    if _has_arabic(text):
        return ar_font_b if bold else ar_font
    return latin_font_b if bold else latin_font


def _draw_r(
    c: canvas.Canvas,
    x_right: float,
    y: float,
    text: Any,
    size: int = 12,
    bold: bool = False,
):
    font_name = _pick_canvas_font(text, bold=bold)
    t = _canvas_text(text)

    c.setFont(font_name, size)
    w = pdfmetrics.stringWidth(t, font_name, size)
    c.drawString(x_right - w, y, t)


def _draw_label_value(
    c: canvas.Canvas,
    x_right: float,
    y: float,
    label_ar: str,
    value: Any,
    size: int = 12,
    bold_label: bool = False,
):
    label_font = _pick_canvas_font(label_ar, bold=bold_label)
    label_t = _canvas_text(label_ar)

    c.setFont(label_font, size)
    lw = pdfmetrics.stringWidth(label_t, label_font, size)
    c.drawString(x_right - lw, y, label_t)

    value_font = _pick_canvas_font(value, bold=False)
    value_t = _canvas_text(value)

    c.setFont(value_font, size)
    vw = pdfmetrics.stringWidth(value_t, value_font, size)
    gap = 10
    c.drawString(x_right - lw - gap - vw, y, value_t)


def transaction_pdf_bytes(tx) -> bytes:
    _ensure_fonts()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    x = w - 18 * mm
    y = h - 18 * mm

    tx_type = str(getattr(tx, "tx_type", "") or "")
    if tx_type == "SALE":
        title = "فاتورة بيع"
    elif tx_type == "PURCHASE":
        title = "فاتورة شراء"
    else:
        title = "سند عملية"

    _draw_r(c, x, y, title, 18, bold=True)
    y -= 12 * mm

    _draw_label_value(c, x, y, "التاريخ:", str(getattr(tx, "date", "")), 12)
    y -= 7 * mm

    _draw_label_value(
        c,
        x,
        y,
        "المرجع:",
        str(getattr(tx, "reference", "") or f"عملية #{getattr(tx, 'id', '')}"),
        12,
    )
    y -= 7 * mm

    name = (getattr(tx, "customer_name", "") or "").strip()
    phone = (getattr(tx, "customer_phone", "") or "").strip()
    cp = getattr(tx, "counterparty", None)

    if cp:
        name = name or (getattr(cp, "name", "") or "")
        phone = phone or (getattr(cp, "phone", "") or "")

    if name:
        _draw_label_value(c, x, y, "العميل:", name, 12)
        y -= 7 * mm

    if phone:
        _draw_label_value(c, x, y, "الجوال:", phone, 12)
        y -= 7 * mm

    y -= 4 * mm

    line = None
    try:
        line = tx.lines.first()
    except Exception:
        pass

    if line:
        try:
            kind = line.get_livestock_kind_display()
        except Exception:
            kind = str(getattr(line, "livestock_kind", ""))

        cls = str(getattr(line, "livestock_class", "") or "")
        if cls and cls != "NONE":
            try:
                cls_label = line.get_livestock_class_display()
            except Exception:
                cls_label = cls
            kind_txt = f"{kind} ({cls_label})"
        else:
            kind_txt = kind

        qty = getattr(line, "quantity", 0)
        unit = getattr(line, "unit_price", 0)

        _draw_label_value(c, x, y, "نوع المواشي:", kind_txt, 12)
        y -= 7 * mm

        _draw_label_value(c, x, y, "الكمية:", str(qty), 12)
        y -= 7 * mm

        _draw_label_value(c, x, y, "سعر الوحدة:", f"{_fmt_money(unit)} ر.س", 12)
        y -= 7 * mm

    total_amount = getattr(tx, "total_amount", 0)
    amount_paid = getattr(tx, "amount_paid", 0)
    amount_due = getattr(tx, "amount_due", 0)

    y -= 3 * mm
    _draw_label_value(c, x, y, "إجمالي العملية:", f"{_fmt_money(total_amount)} ر.س", 14, bold_label=True)
    y -= 9 * mm

    try:
        pay_mode = tx.get_payment_mode_display()
    except Exception:
        pay_mode = str(getattr(tx, "payment_mode", "") or "")

    if pay_mode:
        _draw_label_value(c, x, y, "طريقة الدفع:", pay_mode, 12)
        y -= 7 * mm

    _draw_label_value(c, x, y, "المدفوع:", f"{_fmt_money(amount_paid)} ر.س", 12)
    y -= 7 * mm

    _draw_label_value(c, x, y, "المتبقي (آجل):", f"{_fmt_money(amount_due)} ر.س", 12)
    y -= 7 * mm

    y -= 12 * mm
    _draw_r(c, x, y, "— تم إنشاء هذا المستند من نظام محاسبة المواشي —", 10)

    c.showPage()
    c.save()
    return buf.getvalue()


def summary_pdf_bytes(ctx: dict) -> bytes:
    font, font_b, latin_font, latin_font_b = _ensure_fonts()

    title_txt = ctx.get("title") or "تقرير ملخص (تقارير ذكية)"
    subtitle_txt = ctx.get("subtitle") or "محاسبة المواشي"
    date_from = str(ctx.get("date_from") or "")
    date_to = str(ctx.get("date_to") or "")

    sales = ctx.get("sales_total", Decimal("0.00"))
    purchases = ctx.get("purchases_total", Decimal("0.00"))
    paid = ctx.get("paid_total", Decimal("0.00"))
    due = ctx.get("due_total", Decimal("0.00"))

    breakdown = list(ctx.get("breakdown") or [])
    recent = list(ctx.get("recent") or [])

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
        title=title_txt,
        author=subtitle_txt,
    )

    styles = getSampleStyleSheet()

    st_title = ParagraphStyle(
        "T",
        parent=styles["Title"],
        fontName=font_b,
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
    )
    st_sub = ParagraphStyle(
        "S",
        parent=styles["Normal"],
        fontName=font,
        fontSize=10.5,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#334155"),
    )
    st_h = ParagraphStyle(
        "H",
        parent=styles["Heading3"],
        fontName=font_b,
        fontSize=12.5,
        leading=16,
        alignment=TA_RIGHT,
        spaceBefore=6,
        spaceAfter=4,
    )
    st_p = ParagraphStyle(
        "P",
        parent=styles["Normal"],
        fontName=font,
        fontSize=10.5,
        leading=14,
        alignment=TA_RIGHT,
    )

    st_th_r = ParagraphStyle(
        "TH_R",
        parent=styles["Normal"],
        fontName=font_b,
        fontSize=10.6,
        leading=14,
        alignment=TA_RIGHT,
        textColor=colors.white,
    )
    st_th_c = ParagraphStyle(
        "TH_C",
        parent=styles["Normal"],
        fontName=font_b,
        fontSize=10.6,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.white,
    )
    st_td_ar_r = ParagraphStyle(
        "TD_AR_R",
        parent=styles["Normal"],
        fontName=font,
        fontSize=10.2,
        leading=14,
        alignment=TA_RIGHT,
    )
    st_td_ar_c = ParagraphStyle(
        "TD_AR_C",
        parent=styles["Normal"],
        fontName=font,
        fontSize=10.2,
        leading=14,
        alignment=TA_CENTER,
    )
    st_td_ltr_l = ParagraphStyle(
        "TD_LTR_L",
        parent=styles["Normal"],
        fontName=latin_font,
        fontSize=10.0,
        leading=14,
        alignment=TA_LEFT,
    )
    st_td_ltr_c = ParagraphStyle(
        "TD_LTR_C",
        parent=styles["Normal"],
        fontName=latin_font,
        fontSize=10.0,
        leading=14,
        alignment=TA_CENTER,
    )
    st_td_num = ParagraphStyle(
        "TD_NUM",
        parent=styles["Normal"],
        fontName=latin_font,
        fontSize=10.0,
        leading=14,
        alignment=TA_CENTER,
    )

    def on_page(c, _doc):
        c.saveState()
        ts = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M")
        _draw_r(c, A4[0] - 16 * mm, 9 * mm, f"{subtitle_txt} — تم إنشاء التقرير: {ts}", 9)
        c.setFont(latin_font_b if _doc.page >= 100 else latin_font, 9)
        c.drawString(16 * mm, 9 * mm, str(_doc.page))
        c.restoreState()

    story = []
    story.append(_p(title_txt, st_title, rtl=True))
    story.append(_p(subtitle_txt, st_sub, rtl=True))
    story.append(_p(f"الفترة: {date_from} إلى {date_to}", st_sub, rtl=True))
    story.append(Spacer(1, 6 * mm))

    story.append(_p("الملخص المالي", st_h, rtl=True))
    summary_data = [
        [
            _p("القيمة (ر.س)", st_th_c, rtl=True),
            _p("البند", st_th_r, rtl=True),
        ],
        [
            _p(_money_cell(sales), st_td_num),
            _p("إجمالي المبيعات", st_td_ar_r, rtl=True),
        ],
        [
            _p(_money_cell(purchases), st_td_num),
            _p("إجمالي المشتريات", st_td_ar_r, rtl=True),
        ],
        [
            _p(_money_cell(paid), st_td_num),
            _p("إجمالي المدفوع", st_td_ar_r, rtl=True),
        ],
        [
            _p(_money_cell(due), st_td_num),
            _p("إجمالي الآجل", st_td_ar_r, rtl=True),
        ],
    ]
    t = Table(summary_data, colWidths=[58 * mm, 120 * mm], repeatRows=1)
    t.hAlign = "RIGHT"
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1733")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    story.append(_p("تفصيل النوع/الصنف", st_h, rtl=True))
    if not breakdown:
        story.append(_p("لا توجد بيانات ضمن الفترة المحددة.", st_p, rtl=True))
    else:
        b_data = [[
            _p("الإجمالي (ر.س)", st_th_c, rtl=True),
            _p("الكمية", st_th_c, rtl=True),
            _p("الصنف", st_th_r, rtl=True),
            _p("النوع", st_th_r, rtl=True),
        ]]

        for r in breakdown:
            b_data.append([
                _p(_money_cell(r.get("amt", 0)), st_td_num),
                _p(str(r.get("qty", 0)), st_td_num),
                _p_auto(r.get("cls", "—") or "—", st_td_ar_r, st_td_ltr_l),
                _p_auto(r.get("kind", ""), st_td_ar_r, st_td_ltr_l),
            ])

        bt = Table(b_data, colWidths=[42 * mm, 24 * mm, 38 * mm, 74 * mm], repeatRows=1)
        bt.hAlign = "RIGHT"
        bt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1733")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(bt)

    story.append(Spacer(1, 6 * mm))

    story.append(_p("آخر العمليات", st_h, rtl=True))
    if not recent:
        story.append(_p("لا توجد عمليات ضمن الفترة المحددة.", st_p, rtl=True))
    else:
        r_data = [[
            _p("العميل", st_th_c, rtl=True),
            _p("آجل (ر.س)", st_th_c, rtl=True),
            _p("مدفوع (ر.س)", st_th_c, rtl=True),
            _p("الإجمالي (ر.س)", st_th_c, rtl=True),
            _p("المرجع", st_th_c, rtl=True),
            _p("النوع", st_th_c, rtl=True),
            _p("التاريخ", st_th_c, rtl=True),
        ]]

        for tx in recent[:15]:
            r_data.append([
                _p_auto(tx.get("customer", "—"), st_td_ar_r, st_td_ltr_l),
                _p(_money_cell(tx.get("due", 0)), st_td_num),
                _p(_money_cell(tx.get("paid", 0)), st_td_num),
                _p(_money_cell(tx.get("total", 0)), st_td_num),
                _p_auto(tx.get("reference", ""), st_td_ar_r, st_td_ltr_l),
                _p_auto(tx.get("type", ""), st_td_ar_c, st_td_ltr_c),
                _p(str(tx.get("date", "")), st_td_ltr_c),
            ])

        rt = Table(
            r_data,
            colWidths=[36 * mm, 18 * mm, 18 * mm, 22 * mm, 38 * mm, 18 * mm, 28 * mm],
            repeatRows=1,
        )
        rt.hAlign = "RIGHT"
        rt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1733")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(rt)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()