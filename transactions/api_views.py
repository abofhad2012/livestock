from decimal import Decimal, InvalidOperation

from django.db import transaction as db_transaction
from django.db.models import Sum
from django.utils import timezone

from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import FarmMembership, Profile
from transactions.models import (
    LineType,
    LivestockClass,
    LivestockKind,
    Payment,
    PaymentMethod,
    PaymentMode,
    Transaction,
    TransactionLine,
    TransactionStatus,
    TransactionType,
)


DEFAULT_PURCHASE_REFERENCE_PREFIX = "PO"
DEFAULT_SALE_REFERENCE_PREFIX = "SO"


def _get_farm_for_user(user):
    if not user or not user.is_authenticated:
        return None

    try:
        profile = Profile.objects.select_related("farm").get(user=user, is_active=True)
        if profile.farm and profile.farm.is_active:
            return profile.farm
    except Profile.DoesNotExist:
        pass

    membership = (
        FarmMembership.objects
        .select_related("farm")
        .filter(user=user, is_active=True, farm__is_active=True)
        .order_by("id")
        .first()
    )
    if membership:
        return membership.farm

    return None


def _decimal_payload(value):
    return str(Decimal(value or 0).quantize(Decimal("0.01")))


def _parse_decimal(value, field_name):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid number") from None

    if parsed <= 0:
        raise ValueError(f"{field_name} must be greater than zero")

    return parsed


def _is_tlyan(kind):
    return kind in {
        LivestockKind.HARRI,
        LivestockKind.SAWAKNI,
        LivestockKind.NAIMI,
    }


def _normalize_livestock_class(kind, livestock_class):
    if _is_tlyan(kind):
        return livestock_class
    return LivestockClass.NONE


def _make_reference(prefix, tx_date, tx_id):
    return f"{prefix}-{tx_date:%Y%m%d}-{tx_id:06d}"


def _stock_map_for_farm(farm):
    rows = (
        TransactionLine.objects
        .filter(
            transaction__farm=farm,
            transaction__status=TransactionStatus.POSTED,
        )
        .values(
            "livestock_kind",
            "livestock_class",
            "transaction__tx_type",
            "transaction__is_return",
        )
        .annotate(qty=Sum("quantity"))
    )

    stock_map = {}

    for row in rows:
        qty = row["qty"] or Decimal("0")
        tx_type = row["transaction__tx_type"]

        if tx_type == TransactionType.PURCHASE:
            sign = Decimal("1")
        elif tx_type == TransactionType.SALE:
            sign = Decimal("-1")
        else:
            continue

        if row["transaction__is_return"]:
            sign *= Decimal("-1")

        kind = row["livestock_kind"]
        livestock_class = row["livestock_class"] or LivestockClass.NONE
        key = (kind, livestock_class)

        stock_map[key] = stock_map.get(key, Decimal("0")) + (sign * qty)

    return stock_map


def _stock_payload_for_farm(farm):
    stock_map = _stock_map_for_farm(farm)
    kind_labels = dict(LivestockKind.choices)
    class_labels = dict(LivestockClass.choices)

    items = []
    by_kind = {}

    for (kind, livestock_class), qty in sorted(stock_map.items()):
        if qty == 0:
            continue

        by_kind.setdefault(
            kind,
            {
                "kind": kind,
                "kind_label": str(kind_labels.get(kind, kind)),
                "total": Decimal("0"),
                "classes": {},
            },
        )

        by_kind[kind]["total"] += qty
        by_kind[kind]["classes"][livestock_class] = qty

        items.append(
            {
                "kind": kind,
                "kind_label": str(kind_labels.get(kind, kind)),
                "livestock_class": livestock_class,
                "class_label": str(class_labels.get(livestock_class, livestock_class)),
                "quantity": _decimal_payload(qty),
            }
        )

    by_kind_payload = []
    for kind, data in sorted(by_kind.items()):
        by_kind_payload.append(
            {
                "kind": kind,
                "kind_label": data["kind_label"],
                "total": _decimal_payload(data["total"]),
                "classes": [
                    {
                        "livestock_class": livestock_class,
                        "class_label": str(class_labels.get(livestock_class, livestock_class)),
                        "quantity": _decimal_payload(qty),
                    }
                    for livestock_class, qty in sorted(data["classes"].items())
                ],
            }
        )

    return {
        "items": items,
        "by_kind": by_kind_payload,
    }


def _available_quantity(farm, kind, livestock_class):
    return _stock_map_for_farm(farm).get((kind, livestock_class), Decimal("0"))


def _transaction_payload(tx):
    return {
        "id": tx.id,
        "reference": tx.reference,
        "date": str(tx.date),
        "total_amount": _decimal_payload(tx.total_amount),
        "amount_paid": _decimal_payload(tx.amount_paid),
        "amount_due": _decimal_payload(tx.amount_due),
    }


def _line_payload(line):
    if not line:
        return {
            "kind": "",
            "livestock_class": "",
            "quantity": "0.00",
            "unit_price": "0.00",
            "amount": "0.00",
        }

    return {
        "kind": line.livestock_kind,
        "livestock_class": line.livestock_class,
        "quantity": _decimal_payload(line.quantity),
        "unit_price": _decimal_payload(line.unit_price),
        "amount": _decimal_payload(line.amount),
    }


def _transaction_response(tx, *, idempotent):
    line = tx.lines.first()

    return {
        "ok": True,
        "transaction": _transaction_payload(tx),
        "line": _line_payload(line),
        "idempotent": idempotent,
    }


def _validate_kind_and_class(kind, livestock_class):
    if kind not in LivestockKind.values:
        return None, None, "kind is required"

    if _is_tlyan(kind) and livestock_class not in {
        LivestockClass.JADH,
        LivestockClass.THANI,
    }:
        return None, None, "livestock_class is required for this kind"

    return kind, _normalize_livestock_class(kind, livestock_class), None


def _existing_idempotent_transaction(farm, idempotency_key, expected_type):
    if not idempotency_key:
        return None, None

    existing = Transaction.objects.filter(
        farm=farm,
        idempotency_key=idempotency_key,
    ).first()

    if not existing:
        return None, None

    if existing.tx_type != expected_type:
        return existing, "idempotency key already used for another transaction type"

    return existing, None


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def stock(request):
    if not request.user.has_perm("transactions.view_transaction"):
        return Response(
            {"ok": False, "error": "permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    farm = _get_farm_for_user(request.user)
    if not farm:
        return Response(
            {"ok": False, "error": "farm is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payload = _stock_payload_for_farm(farm)

    return Response(
        {
            "ok": True,
            "farm": {
                "id": farm.id,
                "name": farm.name,
            },
            "items": payload["items"],
            "by_kind": payload["by_kind"],
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def purchase(request):
    if not request.user.has_perm("transactions.add_transaction"):
        return Response(
            {"ok": False, "error": "permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    farm = _get_farm_for_user(request.user)
    if not farm:
        return Response(
            {"ok": False, "error": "farm is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = request.data

    kind = str(data.get("kind") or "").strip()
    livestock_class = str(
        data.get("livestock_class") or data.get("cls") or LivestockClass.NONE
    ).strip()
    idempotency_key = str(data.get("idempotency_key") or "").strip() or None

    kind, livestock_class, error = _validate_kind_and_class(kind, livestock_class)
    if error:
        return Response(
            {"ok": False, "error": error},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        quantity = _parse_decimal(data.get("quantity"), "quantity")
        unit_price = _parse_decimal(data.get("unit_price"), "unit_price")
    except ValueError as exc:
        return Response(
            {"ok": False, "error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    existing, idem_error = _existing_idempotent_transaction(
        farm,
        idempotency_key,
        TransactionType.PURCHASE,
    )
    if idem_error:
        return Response(
            {"ok": False, "error": idem_error},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if existing:
        return Response(
            _transaction_response(existing, idempotent=True),
            status=status.HTTP_200_OK,
        )

    today = timezone.localdate()
    total = (quantity * unit_price).quantize(Decimal("0.01"))

    with db_transaction.atomic():
        tx = Transaction.objects.create(
            farm=farm,
            created_by=request.user,
            tx_type=TransactionType.PURCHASE,
            status=TransactionStatus.POSTED,
            date=today,
            reference="",
            idempotency_key=idempotency_key,
            is_return=False,
            payment_mode=PaymentMode.PAID,
            amount_paid=Decimal("0.00"),
            amount_due=total,
            total_amount=Decimal("0.00"),
        )

        TransactionLine.objects.create(
            transaction=tx,
            line_type=LineType.ANIMAL,
            livestock_kind=kind,
            livestock_class=livestock_class,
            quantity=quantity,
            unit_price=unit_price,
        )

        Payment.objects.create(
            transaction=tx,
            date=today,
            amount=total,
            method=PaymentMethod.CASH,
            created_by=request.user,
        )

        tx.reference = _make_reference(
            DEFAULT_PURCHASE_REFERENCE_PREFIX,
            today,
            tx.id,
        )
        tx.save(update_fields=["reference"])

        tx.refresh_from_db()

    return Response(
        _transaction_response(tx, idempotent=False),
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def sale(request):
    if not request.user.has_perm("transactions.add_transaction"):
        return Response(
            {"ok": False, "error": "permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    farm = _get_farm_for_user(request.user)
    if not farm:
        return Response(
            {"ok": False, "error": "farm is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = request.data

    kind = str(data.get("kind") or "").strip()
    livestock_class = str(
        data.get("livestock_class") or data.get("cls") or LivestockClass.NONE
    ).strip()
    idempotency_key = str(data.get("idempotency_key") or "").strip() or None

    kind, livestock_class, error = _validate_kind_and_class(kind, livestock_class)
    if error:
        return Response(
            {"ok": False, "error": error},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        quantity = _parse_decimal(data.get("quantity"), "quantity")
        unit_price = _parse_decimal(data.get("unit_price"), "unit_price")
    except ValueError as exc:
        return Response(
            {"ok": False, "error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    existing, idem_error = _existing_idempotent_transaction(
        farm,
        idempotency_key,
        TransactionType.SALE,
    )
    if idem_error:
        return Response(
            {"ok": False, "error": idem_error},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if existing:
        return Response(
            _transaction_response(existing, idempotent=True),
            status=status.HTTP_200_OK,
        )

    available = _available_quantity(farm, kind, livestock_class)
    if quantity > available:
        return Response(
            {
                "ok": False,
                "error": "insufficient stock",
                "available": _decimal_payload(available),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    today = timezone.localdate()
    total = (quantity * unit_price).quantize(Decimal("0.01"))

    with db_transaction.atomic():
        tx = Transaction.objects.create(
            farm=farm,
            created_by=request.user,
            tx_type=TransactionType.SALE,
            status=TransactionStatus.POSTED,
            date=today,
            reference="",
            idempotency_key=idempotency_key,
            is_return=False,
            payment_mode=PaymentMode.PAID,
            amount_paid=Decimal("0.00"),
            amount_due=total,
            total_amount=Decimal("0.00"),
        )

        TransactionLine.objects.create(
            transaction=tx,
            line_type=LineType.ANIMAL,
            livestock_kind=kind,
            livestock_class=livestock_class,
            quantity=quantity,
            unit_price=unit_price,
        )

        Payment.objects.create(
            transaction=tx,
            date=today,
            amount=total,
            method=PaymentMethod.CASH,
            created_by=request.user,
        )

        tx.reference = _make_reference(
            DEFAULT_SALE_REFERENCE_PREFIX,
            today,
            tx.id,
        )
        tx.save(update_fields=["reference"])

        tx.refresh_from_db()

    return Response(
        _transaction_response(tx, idempotent=False),
        status=status.HTTP_201_CREATED,
    )
