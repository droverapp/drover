import re
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User


class SignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["first_name", "last_name", "username", "password1", "password2", "contact_number"]

        widgets = {
            "username": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Email"}
            ),
            "first_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "First Name"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Last Name"}
            ),
            "contact_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Contact Number with country code",
                }
            ),
            "sms_optin": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Contact Number with country code",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super(SignUpForm, self).__init__(*args, **kwargs)
        self.fields["password1"].widget = forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Password"}
        )
        self.fields["password2"].widget = forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm Password"}
        )

    def clean_contact_number(self):
        contact_number = self.cleaned_data["contact_number"]
        if "+" not in contact_number:
            raise forms.ValidationError(
                "Contact Number should have country code, e.g. +12025550111",
                code="invalid",
            )
        return contact_number

    def clean_username(self):
        username = self.cleaned_data["username"]
        if "@" not in username:
            raise forms.ValidationError("Invalid email address", code="invalid")
        return username

    def clean_password1(self):
        password1 = self.cleaned_data["password1"]
        regex_character = re.compile(r"[@_!#$%^&*()<>?/\|}{~:]")
        regex_number = re.compile(r"[0-9]")
        if (
            len(password1) < 8
            or not regex_character.search(password1)
            or not regex_number.search(password1)
        ):
            raise forms.ValidationError(
                "Password must be atleast 8 characters long and contain at least 1 special character and 1 number",
                code="invalid",
            )
        return password1
