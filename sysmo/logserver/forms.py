from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.admin.helpers import ActionForm
from django.core.exceptions import ValidationError

def validate_values(value):
    if value < 0:
        raise ValidationError("Plz input the valid values.")

# add the new form in order to get the actions with the parameters
class XForm(ActionForm):
    actions_params = forms.IntegerField(label="===set the values", validators=[validate_values], required=False)
