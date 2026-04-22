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

from accounts.models import FarmMembership, Profile
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
DEFAULT_TERMS_DAYS = 30  # ✅ شهر افتراضي


def _get_farm_for_user(user):
    """
    يرجع المنشأة المرتبطة بالمستخدم الحالي فقط.

    مهم أمنيًا:
    لا نرجع أول Farm في قاعدة البيانات كـ fallback، لأن هذا قد يربط
    المستخدم الجديد ببيانات مستخدم آخر.
    """
    if not user or not user.is_authenticated:
        return None

    # 1) Profile.farm
    try:
        profile = Profile.objects.select_related("farm").get(user=user, is_active=True)
        if profile.farm and profile.farm.is_active:
            return profile.farm
    except Profile.DoesNotExist:
        pass

    # 2) Active FarmMembership
    membership = (
        FarmMembership.objects
        .select_related("farm")
        .filter(user=user, is_active=True, farm__is_active=True)
        .order_by("id")
        .first()
    )
    if membership:
        return membership.farm

    # لا ترجع أول منشأة أبدًا؛ هذا يمنع تسريب بيانات مستخدم آخر.
    return None


def _fmt_money(x, places: int = 2) -> str:
    """
    32200.00 -> 32,200.00
    """
    try:
        d = Decimal(str(x or 0))
    except Exception:
        d = Decimal("0")

    q = Decimal("1") if places == 0 else Decimal("0." + ("0" * (places - 1)) + "1")
    d = d.quantize(q)
    return f"{d:,.{places}f}"


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
    """
    تقرير أعمار الديون (AR Aging) حسب العميل.
    Buckets: current, 1-30, 31-60, 61-90, 90+
    """
    farm = _get_farm_for_user(request.user)
    if not farm:
        return JsonResponse({"ok": False, "error": "لا توجد منشأة (Farm)."}, status=400)

    as_of = _parse_date(request.GET.get("as_of")) or timezone.localdate()

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
        .all()
    )

    def bucket(days_overdue: int) -> str:
        if days_overdue <= 0:
            return "current"
        if days_overdue <= 30:
            return "1_30"
        if days_overdue <= 60:
            return "31_60"
        if days_overdue <= 90:
            return "61_90"
        return "90_plus"

    items_map: dict = {}
    totals = {
        "current": Decimal("0"),
        "1_30": Decimal("0"),
        "31_60": Decimal("0"),
        "61_90": Decimal("0"),
        "90_plus": Decimal("0"),
        "total": Decimal("0"),
    }

    for tx in qs:
        cp = tx.counterparty
        cp_id = cp.id if cp else None
        cp_name = (cp.name if cp else (tx.customer_name or "عميل")).strip()
        cp_phone = (cp.phone if (cp and cp.phone) else (tx.customer_phone or "")).strip()

        key = cp_id if cp_id is not None else f"manual:{cp_phone or cp_name}"

        due = tx.due_date or tx.date or as_of
        days = (as_of - due).days
        b = bucket(days)

        amt = Decimal(tx.amount_due or 0)

        if key not in items_map:
            items_map[key] = {
                "counterparty": {"id": cp_id, "name": cp_name, "phone": cp_phone},
                "current": Decimal("0"),
                "1_30": Decimal("0"),
                "31_60": Decimal("0"),
                "61_90": Decimal("0"),
                "90_plus": Decimal("0"),
                "total": Decimal("0"),
                "invoices": 0,
                "max_days_overdue": 0,
                "min_due_date": None,
            }

        it = items_map[key]
        it[b] += amt
        it["total"] += amt
        it["invoices"] += 1
        if days > it["max_days_overdue"]:
            it["max_days_overdue"] = days
        if it["min_due_date"] is None or due < it["min_due_date"]:
            it["min_due_date"] = due

        totals[b] += amt
        totals["total"] += amt

    # ترتيب: الأكثر تأخرًا ثم الأعلى مبلغًا
    items = list(items_map.values())
    items.sort(key=lambda x: (x["max_days_overdue"], x["total"]), reverse=True)

    # ✅ التغيير المهم: نرجّع أرقام بفاصلة
@require_GET
@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def api_ar_aging(request):
    """
    تقرير أعمار الديون (AR Aging) حسب العميل.
    Buckets: current, 1-30, 31-60, 61-90, 90+
    - يُرجع قيم raw (بدون فاصلة) للحساب.
    - ويُرجع *_display (بفاصلة) للعرض فقط.
    """
    farm = _get_farm_for_user(request.user)
    if not farm:
        return JsonResponse({"ok": False, "error": "لا توجد منشأة (Farm)."}, status=400)

    as_of = _parse_date(request.GET.get("as_of")) or timezone.localdate()

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
        .all()
    )

    def bucket(days_overdue: int) -> str:
        if days_overdue <= 0:
            return "current"
        if days_overdue <= 30:
            return "1_30"
        if days_overdue <= 60:
            return "31_60"
        if days_overdue <= 90:
            return "61_90"
        return "90_plus"

    def dec_raw(x) -> str:
        return str(Decimal(x or 0).quantize(Decimal("0.01")))

    def dec_disp(x) -> str:
        return _fmt_money(Decimal(x or 0), places=2)

    items_map: dict = {}
    totals = {
        "current": Decimal("0"),
        "1_30": Decimal("0"),
        "31_60": Decimal("0"),
        "61_90": Decimal("0"),
        "90_plus": Decimal("0"),
        "total": Decimal("0"),
    }

    for tx in qs:
        cp = tx.counterparty
        cp_id = cp.id if cp else None
        cp_name = (cp.name if cp else (tx.customer_name or "عميل")).strip()
        cp_phone = (cp.phone if (cp and cp.phone) else (tx.customer_phone or "")).strip()

        key = cp_id if cp_id is not None else f"manual:{cp_phone or cp_name}"

        due = tx.due_date or tx.date or as_of
        days = (as_of - due).days
        b = bucket(days)

        amt = Decimal(tx.amount_due or 0)

        if key not in items_map:
            items_map[key] = {
                "counterparty": {"id": cp_id, "name": cp_name, "phone": cp_phone},
                "current": Decimal("0"),
                "1_30": Decimal("0"),
                "31_60": Decimal("0"),
                "61_90": Decimal("0"),
                "90_plus": Decimal("0"),
                "total": Decimal("0"),
                "invoices": 0,
                "max_days_overdue": 0,
                "min_due_date": None,
            }

        it = items_map[key]
        it[b] += amt
        it["total"] += amt
        it["invoices"] += 1
        if days > it["max_days_overdue"]:
            it["max_days_overdue"] = days
        if it["min_due_date"] is None or due < it["min_due_date"]:
            it["min_due_date"] = due

        totals[b] += amt
        totals["total"] += amt

    items = list(items_map.values())
    items.sort(key=lambda x: (x["max_days_overdue"], x["total"]), reverse=True)

    out_items = []
    for it in items:
        out_items.append(
            {
                "counterparty": it["counterparty"],
                # raw (للآلة)
                "current": dec_raw(it["current"]),
                "b1_30": dec_raw(it["1_30"]),
                "b31_60": dec_raw(it["31_60"]),
                "b61_90": dec_raw(it["61_90"]),
                "b90_plus": dec_raw(it["90_plus"]),
                "total": dec_raw(it["total"]),
                # display (للعرض فقط)
                "current_display": dec_disp(it["current"]),
                "b1_30_display": dec_disp(it["1_30"]),
                "b31_60_display": dec_disp(it["31_60"]),
                "b61_90_display": dec_disp(it["61_90"]),
                "b90_plus_display": dec_disp(it["90_plus"]),
                "total_display": dec_disp(it["total"]),
                "invoices": it["invoices"],
                "max_days_overdue": it["max_days_overdue"],
                "min_due_date": str(it["min_due_date"] or ""),
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "as_of": str(as_of),
            "totals": {
                # raw
                "current": dec_raw(totals["current"]),
                "b1_30": dec_raw(totals["1_30"]),
                "b31_60": dec_raw(totals["31_60"]),
                "b61_90": dec_raw(totals["61_90"]),
                "b90_plus": dec_raw(totals["90_plus"]),
                "total": dec_raw(totals["total"]),
                # display
                "current_display": dec_disp(totals["current"]),
                "b1_30_display": dec_disp(totals["1_30"]),
                "b31_60_display": dec_disp(totals["31_60"]),
                "b61_90_display": dec_disp(totals["61_90"]),
                "b90_plus_display": dec_disp(totals["90_plus"]),
                "total_display": dec_disp(totals["total"]),
            },
            "items": out_items,
        }
    )

@require_GET
@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def api_client_whatsapp_reminder(request, pk: int):
    """
    رسالة واتساب جاهزة للعميل المتأخر + تنسيق مبالغ 60,000
    """

    def fmt0(x: Decimal) -> str:
        return f"{Decimal(x):,.0f}"

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
            lines.append(f"- {ref}: {fmt0(amt)} ريال (استحقاق {due})")

    if total_overdue > 0:
        msg = (
            f"السلام عليكم {cp.name}،\n"
            f"نذكّركم بوجود مستحقات متأخرة بقيمة {fmt0(total_overdue)} ريال.\n"
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
            "overdue_total": str(total_overdue),  # أبقيناها raw
            "message": msg,
            "wa_link": _wa_link(cp.phone or "", msg),
        }
    )


@require_GET
@login_required
@permission_required("transactions.view_transaction", raise_exception=True)
def api_ar_clients_summary(request):
    """
    حالة العملاء:
    - paid: لا يوجد رصيد آجل
    - unpaid: يوجد رصيد آجل لكن غير متأخر
    - overdue: يوجد رصيد آجل متأخر
    GET params:
      all=1  -> يعرض كل العملاء (BUYER) حتى لو ما عندهم مبيعات
    """

    def fmt0(x: Decimal) -> str:
        return f"{Decimal(x):,.0f}"

    farm = _get_farm_for_user(request.user)
    if not farm:
        return JsonResponse({"ok": False, "error": "لا توجد منشأة (Farm)."}, status=400)

    today = timezone.localdate()
    include_all = (request.GET.get("all") or "").strip() == "1"

    buyers = Counterparty.objects.filter(farm=farm, party_type=CounterpartyType.BUYER)

    if not include_all:
        cp_ids = (
            Transaction.objects.filter(
                farm=farm,
                tx_type=TransactionType.SALE,
                status=TransactionStatus.POSTED,
                is_return=False,
                counterparty__isnull=False,
            )
            .values_list("counterparty_id", flat=True)
            .distinct()
        )
        buyers = buyers.filter(id__in=cp_ids)

    buyers = buyers.order_by("name").all()

    open_qs = (
        Transaction.objects.filter(
            farm=farm,
            tx_type=TransactionType.SALE,
            status=TransactionStatus.POSTED,
            is_return=False,
            amount_due__gt=0,
            counterparty__in=buyers,
        )
        .select_related("counterparty")
        .order_by("counterparty_id", "due_date", "date", "id")
        .all()
    )

    stats = {}
    for tx in open_qs:
        cp = tx.counterparty
        if not cp:
            continue

        due = tx.due_date or tx.date or today
        days = (today - due).days
        amt = Decimal(tx.amount_due or 0)

        st = stats.setdefault(
            cp.id,
            {
                "outstanding": Decimal("0"),
                "overdue_total": Decimal("0"),
                "min_due_date": None,
                "max_days_overdue": 0,
                "invoices": 0,
            },
        )

        st["outstanding"] += amt
        st["invoices"] += 1

        if days > 0:
            st["overdue_total"] += amt
            if days > st["max_days_overdue"]:
                st["max_days_overdue"] = days

        if st["min_due_date"] is None or due < st["min_due_date"]:
            st["min_due_date"] = due

    items = []
    counts = {"paid": 0, "unpaid": 0, "overdue": 0}

    for cp in buyers:
        st = stats.get(cp.id, None)
        outstanding = st["outstanding"] if st else Decimal("0")
        overdue_total = st["overdue_total"] if st else Decimal("0")
        min_due = st["min_due_date"] if st else None
        max_days = st["max_days_overdue"] if st else 0
        invoices = st["invoices"] if st else 0

        if outstanding <= 0:
            status = "paid"
        elif overdue_total > 0:
            status = "overdue"
        else:
            status = "unpaid"

        counts[status] += 1

        msg = ""
        if status == "overdue":
            msg = (
                f"السلام عليكم {cp.name}،\n"
                f"نذكّركم بوجود مستحقات متأخرة بقيمة {fmt0(overdue_total)} ريال.\n"
                f"إجمالي الرصيد الآجل: {fmt0(outstanding)} ريال.\n"
                "شاكرين لكم، يرجى السداد في أقرب وقت."
            )
        elif status == "unpaid" and min_due:
            msg = (
                f"السلام عليكم {cp.name}،\n"
                f"لديكم رصيد آجل بقيمة {fmt0(outstanding)} ريال.\n"
                f"تاريخ الاستحقاق: {min_due}.\n"
                "شكرًا لكم."
            )

        # ✅ نرجّع قيمتين: raw للفرز/الاستعمال البرمجي + display للفاصلة
        outstanding_raw = str(outstanding.quantize(Decimal("0.01")))
        overdue_raw = str(overdue_total.quantize(Decimal("0.01")))

        items.append(
            {
                "counterparty": {"id": cp.id, "name": cp.name, "phone": cp.phone or ""},
                "status": status,
                "outstanding_raw": outstanding_raw,
                "overdue_total_raw": overdue_raw,
                "outstanding": _fmt_money(outstanding, places=2),
                "overdue_total": _fmt_money(overdue_total, places=2),
                "min_due_date": str(min_due or ""),
                "max_days_overdue": max_days,
                "open_invoices": invoices,
                "wa_link": _wa_link(cp.phone or "", msg) if msg else "",
                "whatsapp_reminder_api": f"/api/clients/{cp.id}/whatsapp-reminder/",
            }
        )

    def sort_key(it):
        pri = {"overdue": 2, "unpaid": 1, "paid": 0}[it["status"]]
        return (pri, Decimal(it["outstanding_raw"]), it["max_days_overdue"])

    items.sort(key=sort_key, reverse=True)

    return JsonResponse({"ok": True, "as_of": str(today), "counts": counts, "items": items})


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

    return JsonResponse(
        {
            "ok": True,
            "tx_id": tx.id,
            "total": str(tx.total_amount),
            "preview_url": f"/reports/tx/{tx.id}/",
            "pdf_url": f"/reports/tx/{tx.id}/pdf/",
        }
    )


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

    due_date = _parse_date((payload.get("due_date") or "").strip() or None)
    terms_days = DEFAULT_TERMS_DAYS

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
        cp = Counterparty.objects.filter(
            farm=farm,
            phone=customer_phone,
            party_type=CounterpartyType.BUYER,
        ).first()

    if not cp and (customer_name or customer_phone):
        name = customer_name or "عميل"
        cp, _ = Counterparty.objects.get_or_create(
            farm=farm,
            name=name,
            party_type=CounterpartyType.BUYER,
            defaults={"phone": customer_phone},
        )

    if cp and customer_phone and (cp.phone or "") != customer_phone:
        cp.phone = customer_phone
        cp.save(update_fields=["phone"])

    if paymode == PaymentMode.PAID:
        amount_paid = total
        amount_due = Decimal("0.00")
    else:
        amount_paid = min(total, max(Decimal("0.00"), paid))
        amount_due = max(Decimal("0.00"), total - amount_paid)

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
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "تجاوز حد الائتمان لهذا العميل. لا يمكن إنشاء بيع آجل بهذا المبلغ.",
                        "outstanding": str(outstanding),
                        "credit_limit": str(limit),
                        "projected": str(projected),
                    },
                    status=400,
                )

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

    return JsonResponse(
        {
            "ok": True,
            "tx_id": tx.id,
            "total": str(tx.total_amount),
            "paid": str(tx.amount_paid),
            "due": str(tx.amount_due),
            "due_date": str(tx.due_date or ""),
            "preview_url": f"/reports/tx/{tx.id}/",
            "pdf_url": f"/reports/tx/{tx.id}/pdf/",
        }
    )


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

    Payment.objects.create(
        farm=farm,
        transaction=tx,
        counterparty=tx.counterparty,
        date=timezone.localdate(),
        amount=pay,
        method=method,
        created_by=request.user,
    )

    return JsonResponse({"ok": True, "paid": str(tx.amount_paid), "due": str(tx.amount_due)})


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

    ret.recalc_total()
    ret.amount_paid = Decimal("0.00")
    ret.amount_due = Decimal("0.00")
    ret.payment_mode = PaymentMode.PAID
    ret.due_date = None
    ret.save(update_fields=["total_amount", "amount_paid", "amount_due", "payment_mode", "due_date", "updated_at"])

    return JsonResponse({"ok": True, "tx_id": ret.id, "preview_url": f"/reports/tx/{ret.id}/"})