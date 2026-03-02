import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Profile
from core.models import Farm

from .models import (
    Counterparty,
    CounterpartyType,
    LivestockClass,
    LivestockKind,
    LineType,
    Payment,
    PaymentMethod,
    PaymentMode,
    Transaction,
    TransactionLine,
    TransactionStatus,
    TransactionType,
)


def _get_farm_for_user(user):
    # 1) profile.farm
    try:
        p = Profile.objects.select_related("farm").get(user=user)
        if p.farm:
            return p.farm
    except Exception:
        pass

    # 2) أول منشأة
    return Farm.objects.order_by("id").first()


def _d(v, default="0"):
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(default)


def _is_tlyan(kind: str) -> bool:
    return kind in {LivestockKind.HARRI, LivestockKind.SAWAKNI, LivestockKind.NAIMI}


def _normalize_cls(kind: str, cls: str) -> str:
    if _is_tlyan(kind):
        return cls
    return LivestockClass.NONE


def _make_reference(prefix: str, dt, tx_id: int) -> str:
    return f"{prefix}-{dt:%Y%m%d}-{tx_id:06d}"


def _get_idempotency_key(request, payload: dict) -> str | None:
    return (payload.get("idempotency_key") or request.headers.get("X-Idempotency-Key") or "").strip() or None


def _available_qty(farm: Farm, kind: str, cls: str) -> Decimal:
    """
    الرصيد = (مشتريات - مبيعات) مع عكس الإشارة للمرتجعات is_return.
    """
    qs = (
        TransactionLine.objects.filter(
            transaction__farm=farm,
            transaction__status=TransactionStatus.POSTED,
            livestock_kind=kind,
            livestock_class=cls,
        )
        .values("transaction__tx_type", "transaction__is_return")
        .annotate(qty=Sum("quantity"))
    )

    avail = Decimal("0")
    for r in qs:
        qty = r["qty"] or Decimal("0")

        if r["transaction__tx_type"] == TransactionType.PURCHASE:
            sign = Decimal("1")
        elif r["transaction__tx_type"] == TransactionType.SALE:
            sign = Decimal("-1")
        else:
            continue

        # المرتجع يعكس اتجاه العملية
        if r["transaction__is_return"]:
            sign *= Decimal("-1")

        avail += sign * qty

    return avail


@require_GET
@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def api_stock(request):
    """
    يرجع مخزون تقديري حسب (نوع/صنف):
    by_kind = { "HARRI": {"total": 100, "JADH": 60, "THANI": 40}, "SHEEP": {"total": 20, "NONE": 20}, ...}
    """
    farm = _get_farm_for_user(request.user)
    if not farm:
        return JsonResponse({"ok": False, "error": "لا توجد منشأة (Farm)."}, status=400)

    qs = (
        TransactionLine.objects.filter(
            transaction__farm=farm,
            transaction__status=TransactionStatus.POSTED,
        )
        .values("livestock_kind", "livestock_class", "transaction__tx_type", "transaction__is_return")
        .annotate(qty=Sum("quantity"))
    )

    stock = {}  # (kind, cls) -> Decimal
    for r in qs:
        kind = r["livestock_kind"]
        cls = r["livestock_class"] or LivestockClass.NONE
        qty = r["qty"] or Decimal("0")

        if r["transaction__tx_type"] == TransactionType.PURCHASE:
            sign = Decimal("1")
        elif r["transaction__tx_type"] == TransactionType.SALE:
            sign = Decimal("-1")
        else:
            continue

        if r["transaction__is_return"]:
            sign *= Decimal("-1")

        stock[(kind, cls)] = stock.get((kind, cls), Decimal("0")) + (sign * qty)

    by_kind = {}
    for (kind, cls), qty in stock.items():
        by_kind.setdefault(kind, {"total": Decimal("0")})
        by_kind[kind]["total"] += qty
        by_kind[kind][cls] = qty

    out = {}
    for k, m in by_kind.items():
        out[k] = {kk: float(v) for kk, v in m.items()}

    return JsonResponse({"ok": True, "by_kind": out})


@require_GET
@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def api_clients_search(request):
    farm = _get_farm_for_user(request.user)
    if not farm:
        return JsonResponse({"ok": False, "error": "لا توجد منشأة (Farm)."}, status=400)

    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"ok": True, "items": []})

    qs = Counterparty.objects.filter(farm=farm).filter(Q(phone__icontains=q) | Q(name__icontains=q)).order_by("name")
    items = [{"id": c.id, "name": c.name, "phone": c.phone or ""} for c in qs[:10]]
    return JsonResponse({"ok": True, "items": items})


@require_POST
@login_required
@permission_required("transactions.add_transaction", raise_exception=True)
@transaction.atomic
def api_purchase(request):
    payload = json.loads(request.body.decode("utf-8") or "{}")

    farm = _get_farm_for_user(request.user)
    if not farm:
        return JsonResponse({"ok": False, "error": "لا توجد منشأة (Farm)."}, status=400)

    idem = _get_idempotency_key(request, payload)
    if idem:
        existing = Transaction.objects.filter(idempotency_key=idem).first()
        if existing:
            return JsonResponse(
                {
                    "ok": True,
                    "tx_id": existing.id,
                    "total": str(existing.total_amount),
                    "preview_url": f"/reports/tx/{existing.id}/",
                    "pdf_url": f"/reports/tx/{existing.id}/pdf/",
                }
            )

    kind = payload.get("kind") or ""
    cls = payload.get("cls") or ""
    qty = _d(payload.get("quantity"), "0")
    unit = _d(payload.get("unit_price"), "0")

    isT = _is_tlyan(kind)

    if kind not in LivestockKind.values:
        return JsonResponse({"ok": False, "error": "اختر نوع المواشي."}, status=400)
    if isT and cls not in {LivestockClass.JADH, LivestockClass.THANI}:
        return JsonResponse({"ok": False, "error": "اختر الصنف (جذع/ثني) للطليان."}, status=400)
    if qty <= 0 or unit <= 0:
        return JsonResponse({"ok": False, "error": "الكمية وسعر الوحدة يجب أن تكون أكبر من صفر."}, status=400)

    today = timezone.now().date()
    total = (qty * unit).quantize(Decimal("0.01"))

    tx = Transaction.objects.create(
        farm=farm,
        created_by=request.user,
        tx_type=TransactionType.PURCHASE,
        status=TransactionStatus.POSTED,
        date=today,
        reference="",
        idempotency_key=idem,
        is_return=False,
        payment_mode=PaymentMode.PAID,
        amount_paid=total,
        amount_due=Decimal("0.00"),
        total_amount=total,
    )
    tx.reference = _make_reference("PO", today, tx.id)
    tx.save(update_fields=["reference"])

    line = TransactionLine.objects.create(
        transaction=tx,
        line_type=LineType.ANIMAL,
        livestock_kind=kind,
        livestock_class=_normalize_cls(kind, cls),
        quantity=qty,
        unit_price=unit,
        description=f"شراء - {dict(TransactionLine._meta.get_field('livestock_kind').choices).get(kind, kind)}",
    )

    tx.total_amount = line.amount
    tx.save(update_fields=["total_amount"])

    return JsonResponse(
        {
            "ok": True,
            "tx_id": tx.id,
            "total": str(tx.total_amount),
            "preview_url": f"/reports/tx/{tx.id}/",
            "pdf_url": f"/reports/tx/{tx.id}/pdf/",
        }
    )


@require_POST
@login_required
@permission_required("transactions.add_transaction", raise_exception=True)
@transaction.atomic
def api_sale(request):
    payload = json.loads(request.body.decode("utf-8") or "{}")

    farm = _get_farm_for_user(request.user)
    if not farm:
        return JsonResponse({"ok": False, "error": "لا توجد منشأة (Farm)."}, status=400)

    idem = _get_idempotency_key(request, payload)
    if idem:
        existing = Transaction.objects.filter(idempotency_key=idem).first()
        if existing:
            return JsonResponse(
                {
                    "ok": True,
                    "tx_id": existing.id,
                    "total": str(existing.total_amount),
                    "paid": str(existing.amount_paid),
                    "due": str(existing.amount_due),
                    "preview_url": f"/reports/tx/{existing.id}/",
                    "pdf_url": f"/reports/tx/{existing.id}/pdf/",
                }
            )

    kind = payload.get("kind") or ""
    cls = payload.get("cls") or ""
    qty = _d(payload.get("quantity"), "0")
    unit = _d(payload.get("unit_price"), "0")

    paymode = payload.get("payment_mode") or PaymentMode.PAID
    paid = _d(payload.get("paid_amount"), "0")

    customer_name = (payload.get("customer_name") or "").strip()
    customer_phone = (payload.get("customer_phone") or "").strip()

    isT = _is_tlyan(kind)

    if kind not in LivestockKind.values:
        return JsonResponse({"ok": False, "error": "اختر نوع المواشي."}, status=400)
    if isT and cls not in {LivestockClass.JADH, LivestockClass.THANI}:
        return JsonResponse({"ok": False, "error": "اختر الصنف (جذع/ثني) للطليان."}, status=400)
    if qty <= 0 or unit <= 0:
        return JsonResponse({"ok": False, "error": "الكمية وسعر الوحدة يجب أن تكون أكبر من صفر."}, status=400)
    if paymode not in PaymentMode.values:
        return JsonResponse({"ok": False, "error": "طريقة دفع غير صحيحة."}, status=400)

    cls_norm = _normalize_cls(kind, cls)

    # ✅ منع البيع فوق الرصيد
    available = _available_qty(farm, kind, cls_norm)
    if qty > available:
        return JsonResponse({"ok": False, "error": f"لا يمكن البيع فوق الرصيد. الرصيد الحالي: {available}"}, status=400)

    today = timezone.now().date()
    total = (qty * unit).quantize(Decimal("0.01"))

    # Counterparty: ابحث بالهاتف أولاً
    cp = None
    if customer_phone:
        cp = Counterparty.objects.filter(farm=farm, phone=customer_phone).first()

    if not cp and (customer_name or customer_phone):
        name = customer_name or "عميل"
        cp, _ = Counterparty.objects.get_or_create(
            farm=farm,
            name=name,
            party_type=CounterpartyType.BUYER,
            defaults={"phone": customer_phone},
        )

    if cp and customer_phone and cp.phone != customer_phone:
        cp.phone = customer_phone
        cp.save(update_fields=["phone"])

    if paymode == PaymentMode.PAID:
        amount_paid = total
        amount_due = Decimal("0.00")
    else:
        amount_paid = min(total, max(Decimal("0.00"), paid))
        amount_due = max(Decimal("0.00"), total - amount_paid)

    # ✅ الآجل لازم رقم جوال (حتى ما تضيع الذمم)
    if paymode == PaymentMode.CREDIT and amount_due > 0 and not customer_phone:
        return JsonResponse({"ok": False, "error": "رقم الجوال مطلوب عند البيع بالآجل."}, status=400)

    tx = Transaction.objects.create(
        farm=farm,
        created_by=request.user,
        tx_type=TransactionType.SALE,
        status=TransactionStatus.POSTED,
        date=today,
        reference="",
        idempotency_key=idem,
        is_return=False,
        counterparty=cp,
        payment_mode=paymode,
        amount_paid=amount_paid,
        amount_due=amount_due,
        customer_name=customer_name,
        customer_phone=customer_phone,
        total_amount=total,
    )
    tx.reference = _make_reference("SO", today, tx.id)
    tx.save(update_fields=["reference"])

    line = TransactionLine.objects.create(
        transaction=tx,
        line_type=LineType.ANIMAL,
        livestock_kind=kind,
        livestock_class=cls_norm,
        quantity=qty,
        unit_price=unit,
        description=f"بيع - {dict(TransactionLine._meta.get_field('livestock_kind').choices).get(kind, kind)}",
    )

    tx.total_amount = line.amount
    tx.save(update_fields=["total_amount"])

    return JsonResponse(
        {
            "ok": True,
            "tx_id": tx.id,
            "total": str(tx.total_amount),
            "paid": str(tx.amount_paid),
            "due": str(tx.amount_due),
            "preview_url": f"/reports/tx/{tx.id}/",
            "pdf_url": f"/reports/tx/{tx.id}/pdf/",
        }
    )


@require_POST
@login_required
@permission_required("transactions.add_payment", raise_exception=True)
@transaction.atomic
def api_payment_add(request):
    payload = json.loads(request.body.decode("utf-8") or "{}")
    farm = _get_farm_for_user(request.user)
    if not farm:
        return JsonResponse({"ok": False, "error": "لا توجد منشأة (Farm)."}, status=400)

    tx_id = int(payload.get("tx_id") or 0)
    amt = _d(payload.get("amount"), "0")
    method = payload.get("method") or PaymentMethod.CASH

    if amt <= 0:
        return JsonResponse({"ok": False, "error": "المبلغ يجب أن يكون أكبر من صفر."}, status=400)

    tx = Transaction.objects.select_related("counterparty").get(id=tx_id, farm=farm)
    if tx.status != TransactionStatus.POSTED or tx.tx_type != TransactionType.SALE or tx.is_return:
        return JsonResponse({"ok": False, "error": "لا يمكن السداد إلا لعملية بيع مرحّلة."}, status=400)

    if tx.amount_due <= 0:
        return JsonResponse({"ok": False, "error": "لا يوجد مبلغ آجل على هذه العملية."}, status=400)

    pay = min(amt, tx.amount_due)

    p = Payment.objects.create(
        farm=farm,
        transaction=tx,
        counterparty=tx.counterparty,
        date=timezone.now().date(),
        amount=pay,
        method=method if method in PaymentMethod.values else PaymentMethod.CASH,
        created_by=request.user,
    )

    tx.amount_paid = (tx.amount_paid + pay).quantize(Decimal("0.01"))
    tx.amount_due = (tx.amount_due - pay).quantize(Decimal("0.01"))
    if tx.amount_due <= 0:
        tx.amount_due = Decimal("0.00")
        tx.payment_mode = PaymentMode.PAID
    tx.save(update_fields=["amount_paid", "amount_due", "payment_mode"])

    return JsonResponse({"ok": True, "payment_id": p.id, "paid": str(tx.amount_paid), "due": str(tx.amount_due)})


@require_POST
@login_required
@permission_required("transactions.change_transaction", raise_exception=True)
def api_tx_cancel(request, tx_id: int):
    farm = _get_farm_for_user(request.user)
    tx = Transaction.objects.get(id=tx_id, farm=farm)

    if tx.status != TransactionStatus.POSTED:
        return JsonResponse({"ok": False, "error": "لا يمكن الإلغاء إلا لعملية مرحّلة."}, status=400)

    tx.status = TransactionStatus.CANCELED
    tx.save(update_fields=["status"])
    return JsonResponse({"ok": True})


@require_POST
@login_required
@permission_required("transactions.add_transaction", raise_exception=True)
@transaction.atomic
def api_tx_return(request, tx_id: int):
    farm = _get_farm_for_user(request.user)
    orig = Transaction.objects.prefetch_related("lines").get(id=tx_id, farm=farm)

    if orig.status != TransactionStatus.POSTED:
        return JsonResponse({"ok": False, "error": "لا يمكن عمل مرتجع إلا لعملية مرحّلة."}, status=400)

    today = timezone.now().date()
    ret = Transaction.objects.create(
        farm=farm,
        created_by=request.user,
        tx_type=orig.tx_type,
        status=TransactionStatus.POSTED,
        date=today,
        reference="",
        is_return=True,
        original_tx=orig,
        payment_mode=PaymentMode.PAID,
        amount_paid=Decimal("0.00"),
        amount_due=Decimal("0.00"),
        customer_name=orig.customer_name,
        customer_phone=orig.customer_phone,
        counterparty=orig.counterparty,
        notes=f"مرتجع عن {orig.reference}",
        total_amount=orig.total_amount,
    )
    ret.reference = _make_reference("RT", today, ret.id)
    ret.save(update_fields=["reference"])

    for ln in orig.lines.all():
        TransactionLine.objects.create(
            transaction=ret,
            line_type=ln.line_type,
            description=f"مرتجع: {ln.description}",
            livestock_kind=ln.livestock_kind,
            livestock_class=ln.livestock_class,
            quantity=ln.quantity,
            unit_price=ln.unit_price,
        )

    ret.recalc_total()
    ret.save(update_fields=["total_amount"])

    return JsonResponse({"ok": True, "tx_id": ret.id, "preview_url": f"/reports/tx/{ret.id}/"})