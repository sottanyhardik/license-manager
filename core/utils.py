from io import BytesIO

from django.http import HttpResponse
from django.template.loader import get_template
from django_tables2 import SingleTableView
from django_tables2.export import ExportMixin
from xhtml2pdf import pisa


class PagedFilteredTableView(ExportMixin, SingleTableView):
    filter_class = None
    context_filter_name = 'filter'
    page_head = None

    def get_queryset(self, **kwargs):
        qs = super(PagedFilteredTableView, self).get_queryset()
        if self.filter_class:
            self.filter = self.filter_class(self.request.GET, queryset=qs)
            return self.filter.qs
        else:
            return qs

    def get_context_data(self, **kwargs):
        context = super(PagedFilteredTableView, self).get_context_data()
        try:
            context[self.context_filter_name] = self.filter
        except:
            pass
        context['page_head'] = self.page_head
        return context


def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("ISO-8859-1")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None