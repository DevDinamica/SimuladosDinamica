from django import forms

from .models import SpreadsheetUpload


class SpreadsheetUploadForm(forms.ModelForm):
    class Meta:
        model = SpreadsheetUpload
        fields = ("file",)
        widgets = {
            "file": forms.ClearableFileInput(
                attrs={
                    "accept": (
                        "application/vnd.openxmlformats-"
                        "officedocument.spreadsheetml.sheet"
                    ),
                }
            )
        }
        labels = {
            "file": "Selecione a planilha preenchida",
        }