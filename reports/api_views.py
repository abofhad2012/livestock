from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q, Sum
from django.utils import timezone

from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import FarmMembership, Profile
from transactions.models import (
    LivestockClass,
    LivestockKind,
    Transaction,
    TransactionLine,
    TransactionStatus,
    TransactionType,
)


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


def _parse_date(value, fallback):
    if not value:
        return fallback

    try:
        return timezone.datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("date must use YYYY-MM-DD format") from None


def _signed_stock_quantity_for_farm(farm):
    rows = (
        TransactionLine.objects
        .filter(
            transaction__farm=farm,
            transaction__status=TransactionStatus.POSTED,
        )
        .values(
            "transaction__tx_type",
            "transaction__is_return",
        )
        .annotate(qty=Sum("quantity"))
    )

    total = Decimal("0.00")

    for row in rows:
        qty = row["qty"] or Decimal("0.00")
        tx_type = row["transaction__tx_type"]

        if tx_type == TransactionType.PURCHASE:
            sign = Decimal("1")
        elif tx_type == TransactionType.SALE:
            sign = Decimal("-1")
        else:
            continue

        if row["transaction__is_return"]:
            sign *= Decimal("-1")

        total += sign * qty

    return total


def _amounts_for_farm_period(farm, date_from, date_to):
    line_qs = TransactionLine.objects.filter(
        transaction__farm=farm,
        transaction__status=TransactionStatus.POSTED,
        transaction__is_return=False,
        transaction__date__range=[date_from, date_to],
    )

    purchases_total = (
        line_qs
        .filter(transaction__tx_type=TransactionType.PURCHASE)
        .aggregate(total=Sum("amount"))
        ["total"]
        or Decimal("0.00")
    )

    sales_total = (
        line_qs
        .filter(transaction__tx_type=TransactionType.SALE)
        .aggregate(total=Sum("amount"))
        ["total"]
        or Decimal("0.00")
    )

    return purchases_total, sales_total


def _recent_transactions_payload(farm, date_from, date_to, limit=10):
    recent = (
        Transaction.objects
        .filter(
            farm=farm,
            status=TransactionStatus.POSTED,
            date__range=[date_from, date_to],
        )
        .order_by("-date", "-id")[:limit]
    )

    type_labels = dict(TransactionType.choices)

    return [
        {
            "id": tx.id,
            "reference": tx.reference,
            "date": str(tx.date),
            "tx_type": tx.tx_type,
            "tx_type_label": str(type_labels.get(tx.tx_type, tx.tx_type)),
            "total_amount": _decimal_payload(tx.total_amount),
            "amount_paid": _decimal_payload(tx.amount_paid),
            "amount_due": _decimal_payload(tx.amount_due),
        }
        for tx in recent
    ]


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def summary(request):
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

    today = timezone.localdate()
    default_from = today.replace(day=1)

    try:
        date_from = _parse_date(request.GET.get("from"), default_from)
        date_to = _parse_date(request.GET.get("to"), today)
    except ValueError as exc:
        return Response(
            {"ok": False, "error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if date_from > date_to:
        return Response(
            {"ok": False, "error": "from date must be before or equal to to date"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tx_qs = Transaction.objects.filter(
        farm=farm,
        status=TransactionStatus.POSTED,
        date__range=[date_from, date_to],
    )

    purchases_count = tx_qs.filter(tx_type=TransactionType.PURCHASE).count()
    sales_count = tx_qs.filter(tx_type=TransactionType.SALE).count()

    purchases_total, sales_total = _amounts_for_farm_period(
        farm,
        date_from,
        date_to,
    )

    current_stock_quantity = _signed_stock_quantity_for_farm(farm)

    return Response(
        {
            "ok": True,
            "farm": {
                "id": farm.id,
                "name": farm.name,
            },
            "period": {
                "from": str(date_from),
                "to": str(date_to),
            },
            "totals": {
                "current_stock_quantity": _decimal_payload(current_stock_quantity),
                "purchases_count": purchases_count,
                "sales_count": sales_count,
                "purchases_total": _decimal_payload(purchases_total),
                "sales_total": _decimal_payload(sales_total),
                "net_sales_minus_purchases": _decimal_payload(
                    sales_total - purchases_total
                ),
            },
            "recent_transactions": _recent_transactions_payload(
                farm,
                date_from,
                date_to,
            ),
        },
        status=status.HTTP_200_OK,
    )
