from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        return self.cleaned_data["email"].lower()


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
