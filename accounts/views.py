from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from core.models import Farm

from .forms import RegisterForm
from .models import FarmMembership, Profile, UserRole


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


@require_http_methods(["GET", "POST"])
@transaction.atomic
def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.is_active = True
            user.is_staff = False
            user.is_superuser = False
            user.save()

            farm = Farm.objects.create(
                name=form.cleaned_data["farm_name"],
                is_active=True,
            )

            Profile.objects.update_or_create(
                user=user,
                defaults={
                    "farm": farm,
                    "full_name": form.cleaned_data.get("full_name", ""),
                    "role": UserRole.OWNER,
                    "is_active": True,
                },
            )

            FarmMembership.objects.update_or_create(
                user=user,
                farm=farm,
                defaults={
                    "role": UserRole.OWNER,
                    "is_active": True,
                },
            )

            operators = _ensure_operators_group()
            user.groups.add(operators)

            login(request, user)

            messages.success(request, "تم إنشاء الحساب بنجاح.")
            return redirect("home")
    else:
        form = RegisterForm()

    return render(request, "registration/register.html", {"form": form})