from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from transactions.models import Transaction, TransactionLine, TransactionType

from .pdf_utils import summary_pdf_bytes, transaction_pdf_bytes


@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def summary(request):
    today = timezone.now().date()
    date_from = request.GET.get("from") or str(today)
    date_to = request.GET.get("to") or str(today)

    qs = Transaction.objects.filter(date__range=[date_from, date_to]).order_by("-date", "-id")

    sales_total = qs.filter(tx_type=TransactionType.SALE).aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")
    purchases_total = qs.filter(tx_type=TransactionType.PURCHASE).aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")
    paid_total = qs.aggregate(s=Sum("amount_paid"))["s"] or Decimal("0.00")
    due_total = qs.aggregate(s=Sum("amount_due"))["s"] or Decimal("0.00")

    kind_map = dict(TransactionLine._meta.get_field("livestock_kind").choices)
    cls_map = dict(TransactionLine._meta.get_field("livestock_class").choices)

    line_qs = TransactionLine.objects.filter(transaction__date__range=[date_from, date_to])
    grouped = (
        line_qs.values("livestock_kind", "livestock_class")
        .annotate(qty=Sum("quantity"), amt=Sum("amount"))
        .order_by("livestock_kind", "livestock_class")
    )

    breakdown = [
        {
            "kind": kind_map.get(r["livestock_kind"], r["livestock_kind"]),
            "cls": cls_map.get(r["livestock_class"], r["livestock_class"]),
            "qty": r["qty"] or 0,
            "amt": r["amt"] or Decimal("0.00"),
        }
        for r in grouped
    ]

    return render(
        request,
        "reports/summary.html",
        {
            "date_from": date_from,
            "date_to": date_to,
            "txs": qs[:200],
            "sales_total": sales_total,
            "purchases_total": purchases_total,
            "paid_total": paid_total,
            "due_total": due_total,
            "breakdown": breakdown,
        },
    )


@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def summary_pdf(request):
    today = timezone.now().date()
    date_from = request.GET.get("from") or str(today)
    date_to = request.GET.get("to") or str(today)

    qs = Transaction.objects.filter(date__range=[date_from, date_to])

    sales_total = qs.filter(tx_type=TransactionType.SALE).aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")
    purchases_total = qs.filter(tx_type=TransactionType.PURCHASE).aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")
    paid_total = qs.aggregate(s=Sum("amount_paid"))["s"] or Decimal("0.00")
    due_total = qs.aggregate(s=Sum("amount_due"))["s"] or Decimal("0.00")

    kind_map = dict(TransactionLine._meta.get_field("livestock_kind").choices)
    cls_map = dict(TransactionLine._meta.get_field("livestock_class").choices)

    line_qs = TransactionLine.objects.filter(transaction__date__range=[date_from, date_to])
    grouped = line_qs.values("livestock_kind", "livestock_class").annotate(qty=Sum("quantity"), amt=Sum("amount"))

    breakdown = [
        {
            "kind": kind_map.get(r["livestock_kind"], r["livestock_kind"]),
            "cls": cls_map.get(r["livestock_class"], r["livestock_class"]),
            "qty": r["qty"] or 0,
            "amt": r["amt"] or Decimal("0.00"),
        }
        for r in grouped
    ]

    pdf = summary_pdf_bytes(
        {
            "date_from": date_from,
            "date_to": date_to,
            "sales_total": sales_total,
            "purchases_total": purchases_total,
            "paid_total": paid_total,
            "due_total": due_total,
            "breakdown": breakdown,
        }
    )
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = 'inline; filename="summary.pdf"'
    return resp


@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def tx_preview(request, tx_id: int):
    tx = get_object_or_404(Transaction.objects.select_related("counterparty").prefetch_related("lines"), pk=tx_id)
    return render(request, "reports/tx_preview.html", {"tx": tx, "line": tx.lines.first()})


@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def tx_pdf(request, tx_id: int):
    tx = get_object_or_404(Transaction.objects.select_related("counterparty").prefetch_related("lines"), pk=tx_id)
    pdf = transaction_pdf_bytes(tx)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="tx-{tx_id}.pdf"'
    return resp


@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def analytics(request):
    today = timezone.now().date()

    def parse_date(v, default):
        try:
            return date.fromisoformat(v)
        except Exception:
            return default

    date_to = parse_date(request.GET.get("to", ""), today)
    date_from = parse_date(request.GET.get("from", ""), date_to - timedelta(days=29))

    # سقف منطقي حتى لا يصير الرسم ثقيل
    if (date_to - date_from).days > 180:
        date_from = date_to - timedelta(days=180)

    qs = Transaction.objects.filter(date__range=[date_from, date_to])

    sales_qs = qs.filter(tx_type=TransactionType.SALE)
    purchases_qs = qs.filter(tx_type=TransactionType.PURCHASE)

    sales_total = sales_qs.aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")
    purchases_total = purchases_qs.aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")
    paid_total = qs.aggregate(s=Sum("amount_paid"))["s"] or Decimal("0.00")
    due_total = qs.aggregate(s=Sum("amount_due"))["s"] or Decimal("0.00")

    net_cash = (paid_total - purchases_total).quantize(Decimal("0.01"))
    net_profit_simple = (sales_total - purchases_total).quantize(Decimal("0.01"))

    kind_map = dict(TransactionLine._meta.get_field("livestock_kind").choices)
    cls_map = dict(TransactionLine._meta.get_field("livestock_class").choices)

    line_qs = TransactionLine.objects.filter(transaction__date__range=[date_from, date_to])
    grouped = (
        line_qs.values("livestock_kind", "livestock_class", "transaction__tx_type")
        .annotate(qty=Sum("quantity"), amt=Sum("amount"))
        .order_by("livestock_kind", "livestock_class")
    )

    cats = {}
    for r in grouped:
        k = r["livestock_kind"]
        c = r["livestock_class"]

        key = f"{k}:{c}"
        kind_label = kind_map.get(k, k)
        cls_label = cls_map.get(c, c)

        label = f"{kind_label} - {cls_label}" if c and c != "NONE" else f"{kind_label}"

        if key not in cats:
            cats[key] = {
                "key": key,
                "kind": k,
                "cls": c,
                "label": label,
                "buy_qty": Decimal("0"),
                "buy_amt": Decimal("0"),
                "sell_qty": Decimal("0"),
                "sell_amt": Decimal("0"),
            }

        if r["transaction__tx_type"] == TransactionType.PURCHASE:
            cats[key]["buy_qty"] += (r["qty"] or Decimal("0"))
            cats[key]["buy_amt"] += (r["amt"] or Decimal("0"))
        elif r["transaction__tx_type"] == TransactionType.SALE:
            cats[key]["sell_qty"] += (r["qty"] or Decimal("0"))
            cats[key]["sell_amt"] += (r["amt"] or Decimal("0"))

    categories = list(cats.values())
    categories.sort(key=lambda x: x["label"])

    for it in categories:
        it["net_qty"] = (it["buy_qty"] - it["sell_qty"])
        it["avg_sell"] = (
            (it["sell_amt"] / it["sell_qty"]).quantize(Decimal("0.01"))
            if it["sell_qty"] else Decimal("0.00")
        )

    def col(attr):
        return [it[attr] for it in categories]

    pivot_rows = [
        {"name": "شراء: عدد", "values": col("buy_qty")},
        {"name": "شراء: إجمالي", "values": col("buy_amt")},
        {"name": "بيع: عدد", "values": col("sell_qty")},
        {"name": "بيع: إجمالي", "values": col("sell_amt")},
        {"name": "مخزون تقديري (شراء-بيع)", "values": col("net_qty")},
        {"name": "متوسط سعر البيع", "values": col("avg_sell")},
    ]

    chart_labels = [it["label"] for it in categories]
    chart_sales = [float(it["sell_amt"]) for it in categories]
    chart_purchases = [float(it["buy_amt"]) for it in categories]

    return render(
        request,
        "reports/analytics.html",
        {
            "date_from": str(date_from),
            "date_to": str(date_to),
            "sales_total": sales_total,
            "purchases_total": purchases_total,
            "paid_total": paid_total,
            "due_total": due_total,
            "net_cash": net_cash,
            "net_profit_simple": net_profit_simple,
            "categories": categories,
            "pivot_rows": pivot_rows,
            "chart_labels": chart_labels,
            "chart_sales": chart_sales,
            "chart_purchases": chart_purchases,
        },
    )