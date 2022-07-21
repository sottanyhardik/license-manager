from django import forms


class ShippingBillForm(forms.Form):
    iec_code = forms.CharField(max_length=30)
    file = forms.FileField()

    def clean(self):
        cleaned_data = super(ShippingBillForm, self).clean()
        file = cleaned_data.get('file')
        if not file:
            raise forms.ValidationError('ALL Fields Are Compulsory!')


class ShippingBillCaptcha(forms.Form):
    captcha = forms.CharField(max_length=30)
    cookies = forms.CharField(max_length=30)

    def clean(self):
        cleaned_data = super(ShippingBillCaptcha, self).clean()
        captcha = cleaned_data.get('captcha')
        cookies = cleaned_data.get('cookies')
        if not captcha and not cookies:
            raise forms.ValidationError('ALL Fields Are Compulsory!')
