from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label="البريد الإلكتروني")
    full_name = forms.CharField(required=False, max_length=150, label="الاسم الكامل")
    farm_name = forms.CharField(required=True, max_length=150, label="اسم المنشأة")

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "full_name", "farm_name", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("هذا البريد مستخدم مسبقًا.")

        return email