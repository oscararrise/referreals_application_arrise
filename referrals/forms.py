from django import forms
from .models import Referral
from jobvite_job_client import obtain_list_applications


class ReferralForm(forms.ModelForm):
    class Meta:
        model = Referral
        fields = [
            "candidate_name",
            "candidate_email",
            "role_name",
        ]
        widgets = {
            "candidate_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter candidate name"
            }),
            "candidate_email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "Enter candidate email"
            }),
            "role_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Start typing a role..."
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Opciones dinámicas desde Redshift
        self.role_name_options = obtain_list_applications()

        # Conectar el datalist al input
        self.fields['role_name'].widget.attrs['list'] = 'role-name-options'

    # Validaciones (para que no dejen vacío nada)
    def clean_candidate_name(self):
        value = (self.cleaned_data.get("candidate_name") or "").strip()
        if not value:
            raise forms.ValidationError("Candidate name is required.")
        return value

    def clean_candidate_email(self):
        value = (self.cleaned_data.get("candidate_email") or "").strip()
        if not value:
            raise forms.ValidationError("Candidate email is required.")
        return value.lower()

    def clean_role_name(self):
        value = (self.cleaned_data.get("role_name") or "").strip()
        if not value:
            raise forms.ValidationError("Role name is required.")
        return value