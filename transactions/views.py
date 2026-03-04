import json
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import quote

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


# =========================
# Helpers
# =========================
DEFAULT_TERMS_DAYS = 30


def _get_farm_for_user(user):
    # 1) profile.farm
    try:
        p = Profile.objects.select_related("farm").get(user=user)
        if p.farm:
            return p.farm
    except Exception:
        pass

    # 2) أول منشأة (Fallback) — يفضّل لاحقًا ربطها بالمستخدم فقط
    return Farm.objects.order_by("id").first()


def _d(v, default="0"):
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(default)


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s))
    except Exception:
        return None


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


def _default_due_date(tx_date: date | None, terms_days: int = DEFAULT_TERMS_DAYS) -> date:
    base = tx_date or timezone.localdate()
    return base + timedelta(days=terms_days)


def _normalize_sa_phone(phone: str) -> str:
    """
    يحاول تحويل:
    05xxxxxxxx -> 9665xxxxxxx
    9665xxxxxxx -> 9665xxxxxxx
    """
    if not phone:
        return ""
    p = "".join(ch for ch in phone if ch.isdigit())
    if len(p) == 10 and p.startswith("05"):
        return "966" + p[1:]
    if len(p) == 12 and p.startswith("966"):
        return p
    return p


def _wa_link(phone: str, message: str) -> str:
    p = _normalize_sa_phone(phone)
    if not p:
        return ""
    return f"https://wa.me/{p}?text={quote(message)}"


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


def _tx_recalc(tx: Transaction, *, terms_days: int = DEFAULT_TERMS_DAYS) -> None:
    """
    إبقاؤها كـ fallback فقط. (الآن models تعمل recalc تلقائيًا)
    """
    if hasattr(tx, "recalc_financials"):
        tx.recalc_financials(terms_days=terms_days, save=True)
        return

    tx.recalc_total()
    tx.save(update_fields=["total_amount", "updated_at"])


# =========================
# Stock / Clients
# =========================
@require_GET
@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def api_stock(request):
    """
    يرجع مخزون تقديري حسب (نوع/صنف)
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


# =========================
# Trader: Aging + WhatsApp Reminder
# =========================
@require_GET
@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def api_ar_aging(request):
    farm = _get_farm_for_user(request.user)
    if not farm:
        return JsonResponse({"ok": False, "error": "لا توجد منشأة (Farm)."}, status=400)

    today = timezone.localdate()

    qs = (
        Transaction.objects.filter(
            farm=farm,
            tx_type=TransactionType.SALE,
            status=TransactionStatus.POSTED,
            is_return=False,
            amount_due__gt=0,
        )
        .select_related("counterparty")
        .order_by("due_date", "date", "id")
    )

    totals = {"current": Decimal("0"), "1_30": Decimal("0"), "31_60": Decimal("0"), "61_90": Decimal("0"), "91_plus": Decimal("0")}

    def _bucket(days: int) -> str:
        if days <= 0:
            return "current"
        if days <= 30:
            return "1_30"
        if days <= 60:
            return "31_60"
        if days <= 90:
            return "61_90"
        return "91_plus"

    by_cp = {}
    rows = []

    for tx in qs[:800]:
        due = tx.due_date or tx.date or today
        days = (today - due).days
        b = _bucket(days)
        amt = Decimal(tx.amount_due or 0)

        totals[b] += amt

        cp = tx.counterparty
        if cp and days > 0:
            rec = by_cp.setdefault(cp.id, {"id": cp.id, "name": cp.name, "phone": cp.phone or "", "overdue_amount": Decimal("0"), "max_days": 0})
            rec["overdue_amount"] += amt
            rec["max_days"] = max(rec["max_days"], days)

        rows.append(
            {
                "id": tx.id,
                "reference": tx.reference or f"TX#{tx.id}",
                "date": str(tx.date),
                "due_date": str(due),
                "days_past_due": days,
                "bucket": b,
                "counterparty_id": cp.id if cp else None,
                "counterparty_name": cp.name if cp else (tx.customer_name or ""),
                "amount_due": str(amt),
                "total_amount": str(tx.total_amount),
            }
        )

    top_overdue = sorted(by_cp.values(), key=lambda x: (x["overdue_amount"], x["max_days"]), reverse=True)[:15]
    for t in top_overdue:
        t["overdue_amount"] = str(t["overdue_amount"])

    return JsonResponse({"ok": True, "as_of": str(today), "totals": {k: str(v) for k, v in totals.items()}, "top_overdue_counterparties": top_overdue, "open_transactions": rows})


@require_GET
@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def api_client_whatsapp_reminder(request, pk: int):
    """
    رسالة واتساب جاهزة للعميل المتأخر + تنسيق مبالغ (بدون .00 وبفواصل)
    """
    from django.utils.formats import number_format

    farm = _get_farm_for_user(request.user)
    if not farm:
        return JsonResponse({"ok": False, "error": "لا توجد منشأة (Farm)."}, status=400)

    cp = Counterparty.objects.filter(farm=farm, id=pk).first()
    if not cp:
        return JsonResponse({"ok": False, "error": "العميل غير موجود."}, status=404)

    today = timezone.localdate()
    qs = (
        Transaction.objects.filter(
            farm=farm,
            tx_type=TransactionType.SALE,
            status=TransactionStatus.POSTED,
            is_return=False,
            counterparty=cp,
            amount_due__gt=0,
        )
        .order_by("due_date", "date", "id")
        .all()
    )

    lines = []
    total_overdue = Decimal("0")
    for tx in qs[:20]:
        due = tx.due_date or tx.date or today
        days = (today - due).days
        if days > 0:
            amt = Decimal(tx.amount_due or 0)
            total_overdue += amt
            ref = tx.reference or f"TX#{tx.id}"
            amt_txt = number_format(amt, decimal_pos=0, force_grouping=True)
            lines.append(f"- {ref}: {amt_txt} ريال (استحقاق {due})")

    if total_overdue > 0:
        total_txt = number_format(total_overdue, decimal_pos=0, force_grouping=True)
        msg = (
            f"السلام عليكم {cp.name}،\n"
            f"نذكّركم بوجود مستحقات متأخرة بقيمة {total_txt} ريال.\n"
            "تفاصيل مختصرة:\n"
            + "\n".join(lines[:10])
            + "\n\nشاكرين لكم، يرجى السداد في أقرب وقت."
        )
    else:
        msg = f"السلام عليكم {cp.name}، للتذكير: نرجو التكرم بمراجعة حسابكم لدينا. شكرًا لكم."

    return JsonResponse(
        {
            "ok": True,
            "counterparty": {"id": cp.id, "name": cp.name, "phone": cp.phone or ""},
            "overdue_total": str(total_overdue),  # قيمة رقمية (للبرمجة)
            "message": msg,
            "wa_link": _wa_link(cp.phone or "", msg),
        }
    )


# =========================
# Purchase
# =========================
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
        existing = Transaction.objects.filter(farm=farm, idempotency_key=idem).first()
        if existing:
            return JsonResponse({"ok": True, "tx_id": existing.id, "total": str(existing.total_amount), "preview_url": f"/reports/tx/{existing.id}/", "pdf_url": f"/reports/tx/{existing.id}/pdf/"})

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

    today = timezone.localdate()
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

    TransactionLine.objects.create(
        transaction=tx,
        line_type=LineType.ANIMAL,
        livestock_kind=kind,
        livestock_class=_normalize_cls(kind, cls),
        quantity=qty,
        unit_price=unit,
        description=f"شراء - {dict(TransactionLine._meta.get_field('livestock_kind').choices).get(kind, kind)}",
    )

    Payment.objects.create(
        farm=farm,
        transaction=tx,
        counterparty=None,
        date=today,
        amount=total,
        method=PaymentMethod.CASH,
        notes="دفعة شراء (تلقائي)",
        created_by=request.user,
    )

    return JsonResponse({"ok": True, "tx_id": tx.id, "total": str(tx.total_amount), "preview_url": f"/reports/tx/{tx.id}/", "pdf_url": f"/reports/tx/{tx.id}/pdf/"})


# =========================
# Sale
# =========================
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
        existing = Transaction.objects.filter(farm=farm, idempotency_key=idem).first()
        if existing:
            return JsonResponse({"ok": True, "tx_id": existing.id, "total": str(existing.total_amount), "paid": str(existing.amount_paid), "due": str(existing.amount_due), "preview_url": f"/reports/tx/{existing.id}/", "pdf_url": f"/reports/tx/{existing.id}/pdf/"})

    kind = payload.get("kind") or ""
    cls = payload.get("cls") or ""
    qty = _d(payload.get("quantity"), "0")
    unit = _d(payload.get("unit_price"), "0")

    paymode = payload.get("payment_mode") or PaymentMode.PAID
    paid = _d(payload.get("paid_amount"), "0")

    customer_name = (payload.get("customer_name") or "").strip()
    customer_phone = (payload.get("customer_phone") or "").strip()

    due_date = _parse_date((payload.get("due_date") or "").strip() or None)
    terms_days = int(payload.get("terms_days") or DEFAULT_TERMS_DAYS)

    method = payload.get("method") or payload.get("payment_method") or PaymentMethod.CASH
    if method not in PaymentMethod.values:
        method = PaymentMethod.CASH

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

    available = _available_qty(farm, kind, cls_norm)
    if qty > available:
        return JsonResponse({"ok": False, "error": f"لا يمكن البيع فوق الرصيد. الرصيد الحالي: {available}"}, status=400)

    today = timezone.localdate()
    total = (qty * unit).quantize(Decimal("0.01"))

    cp = None
    if customer_phone:
        cp = Counterparty.objects.filter(farm=farm, phone=customer_phone, party_type=CounterpartyType.BUYER).first()

    if not cp and (customer_name or customer_phone):
        name = customer_name or "عميل"
        cp, _ = Counterparty.objects.get_or_create(farm=farm, name=name, party_type=CounterpartyType.BUYER, defaults={"phone": customer_phone})

    if cp and customer_phone and (cp.phone or "") != customer_phone:
        cp.phone = customer_phone
        cp.save(update_fields=["phone"])

    if paymode == PaymentMode.PAID:
        amount_paid = total
        amount_due = Decimal("0.00")
    else:
        amount_paid = min(total, max(Decimal("0.00"), paid))
        amount_due = max(Decimal("0.00"), total - amount_paid)

    # ✅ منع الآجل بدون عميل مربوط (حتى لا تضيع الذمم)
    if paymode == PaymentMode.CREDIT and amount_due > 0:
        if not customer_phone:
            return JsonResponse({"ok": False, "error": "رقم الجوال مطلوب عند البيع بالآجل."}, status=400)
        if not cp:
            return JsonResponse({"ok": False, "error": "تعذر إنشاء/ربط عميل لهذا الجوال."}, status=400)

    if paymode == PaymentMode.CREDIT and amount_due > 0 and not due_date:
        due_date = _default_due_date(today, terms_days)

    if paymode == PaymentMode.CREDIT and amount_due > 0 and cp:
        limit = getattr(cp, "credit_limit", None)
        if limit is not None:
            outstanding = (
                Transaction.objects.filter(
                    farm=farm,
                    tx_type=TransactionType.SALE,
                    status=TransactionStatus.POSTED,
                    is_return=False,
                    counterparty=cp,
                    amount_due__gt=0,
                ).aggregate(s=Sum("amount_due"))["s"]
                or Decimal("0.00")
            )
            projected = Decimal(outstanding) + Decimal(amount_due)
            if projected > Decimal(limit):
                return JsonResponse({"ok": False, "error": "تجاوز حد الائتمان لهذا العميل. لا يمكن إنشاء بيع آجل بهذا المبلغ.", "outstanding": str(outstanding), "credit_limit": str(limit), "projected": str(projected)}, status=400)

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
        due_date=due_date,
        customer_name=customer_name,
        customer_phone=customer_phone,
        total_amount=total,
    )
    tx.reference = _make_reference("SO", today, tx.id)
    tx.save(update_fields=["reference"])

    TransactionLine.objects.create(
        transaction=tx,
        line_type=LineType.ANIMAL,
        livestock_kind=kind,
        livestock_class=cls_norm,
        quantity=qty,
        unit_price=unit,
        description=f"بيع - {dict(TransactionLine._meta.get_field('livestock_kind').choices).get(kind, kind)}",
    )

    if amount_paid and amount_paid > 0:
        Payment.objects.create(
            farm=farm,
            transaction=tx,
            counterparty=cp,
            date=today,
            amount=amount_paid,
            method=method,
            notes="دفعة بيع (تلقائي)",
            created_by=request.user,
        )

    return JsonResponse({"ok": True, "tx_id": tx.id, "total": str(tx.total_amount), "paid": str(tx.amount_paid), "due": str(tx.amount_due), "due_date": str(tx.due_date or ""), "preview_url": f"/reports/tx/{tx.id}/", "pdf_url": f"/reports/tx/{tx.id}/pdf/"})


# =========================
# Payments
# =========================
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
    if method not in PaymentMethod.values:
        method = PaymentMethod.CASH

    if amt <= 0:
        return JsonResponse({"ok": False, "error": "المبلغ يجب أن يكون أكبر من صفر."}, status=400)

    tx = Transaction.objects.select_related("counterparty").filter(id=tx_id, farm=farm).first()
    if not tx:
        return JsonResponse({"ok": False, "error": "المعاملة غير موجودة."}, status=404)

    if tx.status != TransactionStatus.POSTED or tx.tx_type != TransactionType.SALE or tx.is_return:
        return JsonResponse({"ok": False, "error": "لا يمكن السداد إلا لعملية بيع مرحّلة."}, status=400)

    if tx.amount_due <= 0:
        return JsonResponse({"ok": False, "error": "لا يوجد مبلغ آجل على هذه العملية."}, status=400)

    pay = min(amt, tx.amount_due).quantize(Decimal("0.01"))

    p = Payment.objects.create(
        farm=farm,
        transaction=tx,  # مهم: نفس instance -> Payment.save سيحدّث tx مباشرة
        counterparty=tx.counterparty,
        date=timezone.localdate(),
        amount=pay,
        method=method,
        created_by=request.user,
    )

    return JsonResponse({"ok": True, "payment_id": p.id, "paid": str(tx.amount_paid), "due": str(tx.amount_due)})


# =========================
# Cancel / Return
# =========================
@require_POST
@login_required
@permission_required("transactions.change_transaction", raise_exception=True)
def api_tx_cancel(request, tx_id: int):
    farm = _get_farm_for_user(request.user)
    tx = Transaction.objects.filter(id=tx_id, farm=farm).first()
    if not tx:
        return JsonResponse({"ok": False, "error": "المعاملة غير موجودة."}, status=404)

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
    orig = Transaction.objects.prefetch_related("lines").filter(id=tx_id, farm=farm).first()
    if not orig:
        return JsonResponse({"ok": False, "error": "المعاملة غير موجودة."}, status=404)

    if orig.status != TransactionStatus.POSTED:
        return JsonResponse({"ok": False, "error": "لا يمكن عمل مرتجع إلا لعملية مرحّلة."}, status=400)

    today = timezone.localdate()
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
        due_date=None,
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
            animal=ln.animal,
            group=ln.group,
        )

    # ثبّت المرتجع كمصفّر ماليًا
    ret.recalc_total()
    ret.amount_paid = Decimal("0.00")
    ret.amount_due = Decimal("0.00")
    ret.payment_mode = PaymentMode.PAID
    ret.due_date = None
    ret.save(update_fields=["total_amount", "amount_paid", "amount_due", "payment_mode", "due_date", "updated_at"])

    return JsonResponse({"ok": True, "tx_id": ret.id, "preview_url": f"/reports/tx/{ret.id}/"})