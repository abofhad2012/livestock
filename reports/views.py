from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from accounts.models import Profile
from core.models import Farm
from transactions.models import Transaction, TransactionLine, TransactionStatus, TransactionType

from .pdf_fonts import register_arabic_fonts
from .pdf_utils import summary_pdf_bytes, transaction_pdf_bytes


def _parse_date(v: str, default: date) -> date:
    try:
        return date.fromisoformat(v)
    except Exception:
        return default


def _normalize_date_range(date_from: date, date_to: date):
    if date_from > date_to:
        return date_to, date_from
    return date_from, date_to


def _get_farm_for_user(user):
    try:
        p = Profile.objects.select_related("farm").get(user=user)
        if p.farm:
            return p.farm
    except Exception:
        pass

    return Farm.objects.order_by("id").first()


def _tx_base_qs(user, date_from: date, date_to: date):
    farm = _get_farm_for_user(user)
    qs = Transaction.objects.filter(
        farm=farm,
        date__range=[date_from, date_to],
        status=TransactionStatus.POSTED,
        is_return=False,
    )
    return farm, qs


def _build_breakdown(farm, date_from: date, date_to: date):
    kind_map = dict(TransactionLine._meta.get_field("livestock_kind").choices)
    cls_map = dict(TransactionLine._meta.get_field("livestock_class").choices)

    line_qs = TransactionLine.objects.filter(
        transaction__farm=farm,
        transaction__status=TransactionStatus.POSTED,
        transaction__is_return=False,
        transaction__date__range=[date_from, date_to],
    )
    grouped = (
        line_qs.values("livestock_kind", "livestock_class")
        .annotate(qty=Sum("quantity"), amt=Sum("amount"))
        .order_by("livestock_kind", "livestock_class")
    )

    return [
        {
            "kind": kind_map.get(r["livestock_kind"], r["livestock_kind"]),
            "cls": cls_map.get(r["livestock_class"], r["livestock_class"]),
            "qty": r["qty"] or 0,
            "amt": r["amt"] or Decimal("0.00"),
        }
        for r in grouped
    ]


def _build_summary_data(user, date_from: date, date_to: date):
    date_from, date_to = _normalize_date_range(date_from, date_to)

    farm, qs = _tx_base_qs(user, date_from, date_to)
    qs = qs.order_by("-date", "-id")

    sales_total = (
        qs.filter(tx_type=TransactionType.SALE)
        .aggregate(s=Sum("total_amount"))["s"]
        or Decimal("0.00")
    )
    purchases_total = (
        qs.filter(tx_type=TransactionType.PURCHASE)
        .aggregate(s=Sum("total_amount"))["s"]
        or Decimal("0.00")
    )
    paid_total = qs.aggregate(s=Sum("amount_paid"))["s"] or Decimal("0.00")
    due_total = qs.aggregate(s=Sum("amount_due"))["s"] or Decimal("0.00")

    return {
        "farm": farm,
        "qs": qs,
        "date_from": date_from,
        "date_to": date_to,
        "sales_total": sales_total,
        "purchases_total": purchases_total,
        "paid_total": paid_total,
        "due_total": due_total,
        "breakdown": _build_breakdown(farm, date_from, date_to),
        "farm_name": getattr(farm, "name", "") or "محاسبة المواشي",
    }


def _build_recent_transactions(qs, limit: int = 15):
    txs = qs.select_related("counterparty")[:limit]
    recent = []

    for tx in txs:
        tx_type_label = (
            "بيع"
            if tx.tx_type == TransactionType.SALE
            else (
                "شراء"
                if tx.tx_type == TransactionType.PURCHASE
                else str(tx.tx_type)
            )
        )

        customer = ""
        try:
            if getattr(tx, "counterparty", None):
                customer = tx.counterparty.name or ""
        except Exception:
            pass

        if not customer:
            customer = (getattr(tx, "customer_name", "") or "").strip()

        recent.append(
            {
                "date": tx.date,
                "type": tx_type_label,
                "reference": getattr(tx, "reference", "") or f"TX#{tx.id}",
                "total": tx.total_amount or Decimal("0.00"),
                "paid": getattr(tx, "amount_paid", Decimal("0.00")) or Decimal("0.00"),
                "due": getattr(tx, "amount_due", Decimal("0.00")) or Decimal("0.00"),
                "customer": customer or "—",
            }
        )

    return recent


@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def summary(request):
    today = timezone.localdate()
    date_from = _parse_date(request.GET.get("from") or str(today), today)
    date_to = _parse_date(request.GET.get("to") or str(today), today)

    data = _build_summary_data(request.user, date_from, date_to)

    return render(
        request,
        "reports/summary.html",
        {
            "date_from": str(data["date_from"]),
            "date_to": str(data["date_to"]),
            "txs": data["qs"][:200],
            "sales_total": data["sales_total"],
            "purchases_total": data["purchases_total"],
            "paid_total": data["paid_total"],
            "due_total": data["due_total"],
            "breakdown": data["breakdown"],
            "farm_name": data["farm_name"],
        },
    )


@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def summary_pdf(request):
    today = timezone.localdate()
    date_from = _parse_date(request.GET.get("from") or str(today), today)
    date_to = _parse_date(request.GET.get("to") or str(today), today)

    data = _build_summary_data(request.user, date_from, date_to)

    register_arabic_fonts()

    pdf = summary_pdf_bytes(
        {
            "date_from": str(data["date_from"]),
            "date_to": str(data["date_to"]),
            "sales_total": data["sales_total"],
            "purchases_total": data["purchases_total"],
            "paid_total": data["paid_total"],
            "due_total": data["due_total"],
            "breakdown": data["breakdown"],
            "recent": _build_recent_transactions(data["qs"]),
            "title": "تقرير ملخص (تقارير ذكية)",
            "subtitle": data["farm_name"],
        }
    )

    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = (
        f'inline; filename="summary_{data["date_from"]}_{data["date_to"]}.pdf"'
    )
    return resp


@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def tx_preview(request, tx_id: int):
    farm = _get_farm_for_user(request.user)
    tx = get_object_or_404(
        Transaction.objects.select_related("counterparty").prefetch_related("lines"),
        pk=tx_id,
        farm=farm,
    )
    return render(
        request,
        "reports/tx_preview.html",
        {"tx": tx, "line": tx.lines.first()},
    )


@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def tx_pdf(request, tx_id: int):
    farm = _get_farm_for_user(request.user)
    tx = get_object_or_404(
        Transaction.objects.select_related("counterparty").prefetch_related("lines"),
        pk=tx_id,
        farm=farm,
    )

    register_arabic_fonts()

    pdf = transaction_pdf_bytes(tx)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="tx-{tx_id}.pdf"'
    return resp


@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def analytics(request):
    today = timezone.localdate()

    # الافتراضي: عرض حركة اليوم فقط حتى لا تتراكم أرقام آخر 30 يوم تلقائياً
    date_to = _parse_date(request.GET.get("to") or str(today), today)
    date_from = _parse_date(
        request.GET.get("from") or str(date_to),
        date_to,
    )

    date_from, date_to = _normalize_date_range(date_from, date_to)

    if (date_to - date_from).days > 180:
        date_from = date_to - timedelta(days=180)

    farm, qs = _tx_base_qs(request.user, date_from, date_to)

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

    line_qs = TransactionLine.objects.filter(
        transaction__farm=farm,
        transaction__status=TransactionStatus.POSTED,
        transaction__is_return=False,
        transaction__date__range=[date_from, date_to],
    )
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
        it["net_qty"] = it["buy_qty"] - it["sell_qty"]
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
            "farm_name": getattr(farm, "name", "") or "محاسبة المواشي",
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