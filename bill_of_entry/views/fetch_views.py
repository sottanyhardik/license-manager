import json
import math

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import FormView
from django.db.models import Q

from .common import forms, bill_of_entry, logger
from lmanagement.tasks import fetch_data_to_model


class BillOfEntryFetchView(FormView):
    template_name = 'bill_of_entry/fetch.html'
    form_class = forms.BillOfEntryCaptcha

    def get_context_data(self, **kwargs):
        context = super(BillOfEntryFetchView, self).get_context_data(**kwargs)

        # fetch cookies and csrf using the amended script (returns cookie dict, csrf)
        try:
            from bill_of_entry.scripts.boe import fetch_cookies, fetch_captcha
            cookies, csrftoken = fetch_cookies(verify=False)
        except Exception as e:
            logger.exception("Error fetching cookies/csrf: %s", e)
            cookies, csrftoken = {}, None

        # attempt to fetch captcha image (may return None on error)
        captcha_url = None
        try:
            captcha_url = fetch_captcha(cookies, verify=False)
        except Exception as e:
            logger.exception("Error fetching captcha: %s", e)
            captcha_url = None

        context['captcha_url'] = captcha_url
        context['fetch_cookies'] = json.dumps(cookies)
        context['csrftoken'] = csrftoken

        # remaining count and estimate of captchas needed
        from ..models import BillOfEntryModel
        remaining_qs = BillOfEntryModel.objects.filter(
            Q(is_fetch=False) | Q(appraisement=None) | Q(ooc_date=None) | Q(ooc_date='N.A.')
        ).exclude(failed__gte=5)
        context['remain_count'] = remaining_qs.count()
        context['remain_captcha'] = math.ceil(context['remain_count'] / 3) if context['remain_count'] else 0

        return context

    def post(self, request, *args, **kwargs):
        captcha = self.request.POST.get('captcha')
        try:
            cookies = json.loads(self.request.POST.get('cookies') or '{}')
        except Exception:
            cookies = {}
        csrftoken = self.request.POST.get('csrftoken')

        if not captcha:
            logger.warning("No captcha provided in POST.")
            return self.form_invalid(self.get_form())

        from ..models import BillOfEntryModel
        data_list = BillOfEntryModel.objects.filter(
            Q(is_fetch=False) | Q(appraisement=None) | Q(ooc_date=None) | Q(ooc_date='N.A.')
        ).exclude(failed__gte=5).order_by('-bill_of_entry_date')

        try:
            from bill_of_entry.scripts.utils import port_dict
        except Exception:
            logger.exception("Could not import port_dict from bill_of_entry.scripts.utils")
            port_dict = {}

        for data in data_list:
            try:
                fetch_data_to_model.delay(cookies, csrftoken, port_dict, captcha, data.pk)
            except Exception as e:
                logger.exception("Failed to enqueue fetch_data_to_model for pk=%s: %s", data.pk, e)

        return HttpResponseRedirect(reverse('bill-of-entry-list'))
