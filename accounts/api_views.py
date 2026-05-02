from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import FarmMembership, Profile, UserRole
from core.models import Farm


def _ensure_operators_group():
    group, _ = Group.objects.get_or_create(name="Operators")

    perms = Permission.objects.filter(
        content_type__app_label__in=[
            "transactions",
            "reports",
            "herd",
            "core",
        ]
    )

    group.permissions.set(perms)
    return group


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


def _user_payload(user):
    profile = Profile.objects.filter(user=user).first()
    return {
        "id": user.id,
        "username": user.get_username(),
        "email": user.email or "",
        "full_name": profile.full_name if profile else "",
        "phone": profile.phone if profile else "",
    }


def _farm_payload(farm):
    if not farm:
        return None

    return {
        "id": farm.id,
        "name": farm.name,
        "city": farm.city,
    }


def _auth_payload(user, token=None):
    payload = {
        "ok": True,
        "user": _user_payload(user),
        "farm": _farm_payload(_get_farm_for_user(user)),
    }

    if token is not None:
        payload["token"] = token.key

    return payload


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    User = get_user_model()
    data = request.data

    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    email = str(data.get("email") or "").strip()
    full_name = str(data.get("full_name") or "").strip()
    phone = str(data.get("phone") or "").strip()
    farm_name = str(data.get("farm_name") or "").strip()

    if not username:
        return Response({"ok": False, "error": "username is required"}, status=status.HTTP_400_BAD_REQUEST)

    if not password:
        return Response({"ok": False, "error": "password is required"}, status=status.HTTP_400_BAD_REQUEST)

    if not farm_name:
        return Response({"ok": False, "error": "farm_name is required"}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username__iexact=username).exists():
        return Response({"ok": False, "error": "username already exists"}, status=status.HTTP_400_BAD_REQUEST)

    user = User(username=username, email=email)
    if full_name:
        user.first_name = full_name[:150]

    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        return Response({"ok": False, "errors": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        user.set_password(password)
        user.save()

        farm = Farm.objects.create(
            name=farm_name,
            is_active=True,
        )

        Profile.objects.create(
            user=user,
            farm=farm,
            full_name=full_name,
            phone=phone,
            role=UserRole.OWNER,
            is_active=True,
        )

        FarmMembership.objects.create(
            user=user,
            farm=farm,
            role=UserRole.OWNER,
            is_active=True,
        )

        operators = _ensure_operators_group()
        user.groups.add(operators)

        token, _ = Token.objects.get_or_create(user=user)

    return Response(_auth_payload(user, token), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    username = str(request.data.get("username") or "").strip()
    password = str(request.data.get("password") or "")

    user = authenticate(request, username=username, password=password)
    if not user:
        return Response({"ok": False, "error": "invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

    token, _ = Token.objects.get_or_create(user=user)
    return Response(_auth_payload(user, token), status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(_auth_payload(request.user), status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def logout(request):
    if request.auth:
        request.auth.delete()
    else:
        Token.objects.filter(user=request.user).delete()

    return Response({"ok": True}, status=status.HTTP_200_OK)
