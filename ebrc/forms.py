from django import forms


class EbrcForm(forms.Form):
    iec = forms.CharField(max_length=30)
    ifsc = forms.CharField(max_length=254, required=False)
    file = forms.FileField(required=False)

    def clean(self):
        cleaned_data = super(EbrcForm, self).clean()
        iec = cleaned_data.get('iec')
        ifsc = cleaned_data.get('ifsc')
        file = cleaned_data.get('file')
        if not iec and not ifsc and not file:
            raise forms.ValidationError('ALL Fields Are Compulsory!')


class EbrcCaptcha(forms.Form):
    captcha = forms.CharField(max_length=30)
    cookies = forms.CharField(max_length=30)

    def clean(self):
        cleaned_data = super(EbrcCaptcha, self).clean()
        captcha = cleaned_data.get('captcha')
        cookies = cleaned_data.get('cookies')
        if not captcha and not cookies:
            raise forms.ValidationError('ALL Fields Are Compulsory!')
