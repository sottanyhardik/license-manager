"""
Shared DRF passthrough renderers for report exports.

DRF's content negotiation intercepts the `?format=` query param
(`URL_FORMAT_OVERRIDE`, see `rest_framework.negotiation.DefaultContentNegotiation.
filter_renderers`) and raises `Http404` when no registered renderer's
`.format` matches it — this happens in `APIView.initial()`, BEFORE the
view's own `get()` ever runs, regardless of what the view intends to do
with that query param itself. A plain `APIView` with this project's global
`DEFAULT_RENDERER_CLASSES = (JSONRenderer,)` therefore 404s on `?format=excel`
or `?format=pdf` even though the view has its own, entirely separate
`request.GET.get('format')` check to decide how to respond.

These renderers exist purely to satisfy that negotiation step. The view
itself always returns a plain Django `HttpResponse` for the binary export —
DRF never actually calls `.render()` on these.
"""
from rest_framework.renderers import BaseRenderer


class ExcelPassthroughRenderer(BaseRenderer):
    """Registers 'excel' as an accepted `?format=` value so DRF's content
    negotiation doesn't 404 before the view runs. See module docstring."""
    media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    format = 'excel'
    charset = None
    render_style = 'binary'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data  # never reached — the view returns HttpResponse directly.


class PdfPassthroughRenderer(BaseRenderer):
    """Registers 'pdf' as an accepted `?format=` value — see module docstring."""
    media_type = 'application/pdf'
    format = 'pdf'
    charset = None
    render_style = 'binary'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data  # never reached — the view returns HttpResponse directly.
