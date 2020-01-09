from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User


class SignUpForm(UserCreationForm):

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'password1', 'password2', 'contact_number']

        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Number with country code'})
        }
    
    def __init__(self, *args, **kwargs):
        super(SignUpForm, self).__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
        self.fields['password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'})

    def clean_contact_number(self):
        contact_number = self.cleaned_data['contact_number']
        if '+' not in contact_number:
            raise forms.ValidationError("Contact Number should have country code, e.g. +12025550111", code='invalid')
        return contact_number