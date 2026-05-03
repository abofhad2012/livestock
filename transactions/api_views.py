from decimal import Decimal

from django.db.models import Sum

from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import FarmMembership, Profile
from transactions.models import (
    LivestockClass,
    LivestockKind,
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

    return Response(
        {
            "ok": True,
            "farm": {
                "id": farm.id,
                "name": farm.name,
            },
            "items": items,
            "by_kind": by_kind_payload,
        },
        status=status.HTTP_200_OK,
    )
