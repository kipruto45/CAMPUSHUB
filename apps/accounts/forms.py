"""
Custom forms for accounts app.
"""

from django import forms
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm
from django.contrib.auth.forms import UsernameField
from django.utils.translation import gettext_lazy as _
import unicodedata


class SafeUsernameField(UsernameField):
    """
    A safer UsernameField that properly handles None values.
    
    This fixes the issue where Django's UsernameField.to_python() tries to call
    len() on None values, causing a TypeError.
    """

    def to_python(self, value):
        value = super(forms.CharField, self).to_python(value)
        if value is None:
            return ""
        if self.max_length is not None and len(value) > self.max_length:
            return value
        return unicodedata.normalize("NFKC", value)


class UserChangeForm(BaseUserChangeForm):
    """
    Custom UserChangeForm that uses SafeUsernameField to handle None values.
    """
    username = SafeUsernameField(
        label=_("Username"),
        max_length=150,
        required=False,
        help_text=_(
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
    )


class UserCreationForm(BaseUserCreationForm):
    """
    Custom UserCreationForm that uses SafeUsernameField to handle None values.
    """
    username = SafeUsernameField(
        label=_("Username"),
        max_length=150,
        required=False,
        help_text=_(
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
    )
