import ast

from django.http import HttpResponseRedirect
from django.shortcuts import render
import json

# Create your views here.
from django.urls import reverse
from django.views.generic import FormView

from bill_of_entry.forms import BillOfEntryCaptcha
from bill_of_entry.scripts.boe import fetch_cookies_scrap, fetch_captcha_scrap
from eScrap.scripts import fetch_iec_details
from scripts.BOE import fetch_cookies


class IECFetchView(FormView):
    template_name = 'scrap/fetch.html'
    form_class = BillOfEntryCaptcha

    def post(self, request, *args, **kwargs):
        captcha = self.request.POST.get('captcha')
        cookies = ast.literal_eval(self.request.POST.get('cookies'))
        csrftoken = self.request.POST.get('csrftoken')
        status = fetch_iec_details(cookies, captcha)
        return HttpResponseRedirect(reverse('fetch_iec_details'))

    def get_context_data(self, **kwargs):
        context = super(IECFetchView, self).get_context_data(**kwargs)
        cookies, csrftoken = fetch_cookies_scrap()
        context['captcha_url'], cookies = fetch_captcha_scrap(cookies)
        context['cookies'] = cookies
        context['csrftoken'] = csrftoken
        return context

    def post(self, request, *args, **kwargs):
        captcha = self.request.POST.get('captcha')
        import json
        cookies = ast.literal_eval(self.request.POST.get('cookies'))
        print(cookies)
        csrftoken = self.request.POST.get('csrftoken')
        status = True
        status = fetch_iec_details(cookies, captcha)
        return HttpResponseRedirect(reverse('fetch_iec_details'))
