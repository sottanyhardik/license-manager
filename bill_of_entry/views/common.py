from decimal import Decimal

import logging
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, FormView, DeleteView, UpdateView, CreateView
from django_filters.views import FilterView
from django_tables2 import SingleTableView
from django_tables2.export import ExportMixin
from easy_pdf.views import PDFTemplateResponseMixin
from extra_views import UpdateWithInlinesView, InlineFormSetFactory

# app-specific imports (relative to package)
from ..models import RowDetails
from lmanagement.tasks import fetch_data_to_model
from .. import forms, tables, filters
from .. import models as bill_of_entry

logger = logging.getLogger(__name__)
