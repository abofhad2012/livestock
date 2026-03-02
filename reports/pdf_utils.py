from io import BytesIO

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


_FONT_READY = False


def _ensure_font():
    global _FONT_READY
    if _FONT_READY:
        return
    # خط ويندوز يدعم العربية
    pdfmetrics.registerFont(TTFont("Arial", r"C:\Windows\Fonts\arial.ttf"))
    _FONT_READY = True


def ar(text: str) -> str:
    text = "" if text is None else str(text)
    return get_display(arabic_reshaper.reshape(text))


def draw_r(c: canvas.Canvas, x_right: float, y: float, text: str, size: int = 12):
    _ensure_font()
    c.setFont("Arial", size)
    t = ar(text)
    w = pdfmetrics.stringWidth(t, "Arial", size)
    c.drawString(x_right - w, y, t)


def transaction_pdf_bytes(tx):
    _ensure_font()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    x = w - 2 * cm
    y = h - 2 * cm

    title = "فاتورة بيع" if tx.tx_type == "SALE" else "إيصال شراء"
    draw_r(c, x, y, title, 18); y -= 1.0 * cm

    draw_r(c, x, y, f"التاريخ: {tx.date}", 12); y -= 0.7 * cm
    draw_r(c, x, y, f"المرجع: {tx.reference or '-'}", 12); y -= 0.7 * cm

    if tx.customer_name or tx.counterparty_id:
        name = tx.customer_name or (tx.counterparty.name if tx.counterparty_id else "")
        phone = tx.customer_phone or (tx.counterparty.phone if tx.counterparty_id else "")
        draw_r(c, x, y, f"العميل: {name}", 12); y -= 0.7 * cm
        if phone:
            draw_r(c, x, y, f"الجوال: {phone}", 12); y -= 0.7 * cm

    # Line (أول بند)
    line = tx.lines.first()
    if line:
        draw_r(c, x, y, f"نوع المواشي: {line.get_livestock_kind_display()}", 12); y -= 0.7 * cm
        if line.livestock_class and line.livestock_class != "NONE":
            draw_r(c, x, y, f"الصنف: {line.get_livestock_class_display()}", 12); y -= 0.7 * cm
        draw_r(c, x, y, f"الكمية: {line.quantity}", 12); y -= 0.7 * cm
        draw_r(c, x, y, f"سعر الوحدة: {line.unit_price} ريال", 12); y -= 0.7 * cm

    y -= 0.3 * cm
    draw_r(c, x, y, f"إجمالي العملية: {tx.total_amount} ريال", 14); y -= 0.9 * cm
    draw_r(c, x, y, f"طريقة الدفع: {tx.get_payment_mode_display()}", 12); y -= 0.7 * cm
    draw_r(c, x, y, f"المدفوع: {tx.amount_paid} ريال", 12); y -= 0.7 * cm
    draw_r(c, x, y, f"المتبقي (آجل): {tx.amount_due} ريال", 12); y -= 0.7 * cm

    y -= 0.8 * cm
    draw_r(c, x, y, "— تم إنشاء هذا المستند من نظام محاسبة المواشي —", 11)

    c.showPage()
    c.save()
    return buf.getvalue()


def summary_pdf_bytes(context: dict):
    _ensure_font()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    x = w - 2 * cm
    y = h - 2 * cm

    draw_r(c, x, y, "تقرير ملخص (تقارير ذكية)", 18); y -= 1.0 * cm
    draw_r(c, x, y, f"الفترة: {context['date_from']} → {context['date_to']}", 12); y -= 0.9 * cm

    draw_r(c, x, y, f"إجمالي المبيعات: {context['sales_total']} ريال", 12); y -= 0.7 * cm
    draw_r(c, x, y, f"إجمالي المشتريات: {context['purchases_total']} ريال", 12); y -= 0.7 * cm
    draw_r(c, x, y, f"إجمالي المدفوع: {context['paid_total']} ريال", 12); y -= 0.7 * cm
    draw_r(c, x, y, f"إجمالي الآجل: {context['due_total']} ريال", 12); y -= 0.7 * cm

    y -= 0.6 * cm
    draw_r(c, x, y, "تفصيل الأصناف (حسب البنود):", 13); y -= 0.8 * cm

    for row in context["breakdown"][:20]:
        draw_r(c, x, y, f"{row['kind']} / {row['cls']}  —  عدد: {row['qty']}  —  إجمالي: {row['amt']} ريال", 11)
        y -= 0.6 * cm
        if y < 2 * cm:
            c.showPage()
            y = h - 2 * cm

    c.showPage()
    c.save()
    return buf.getvalue()