# from django import forms
# from django_filters.widgets import SuffixedMultiWidget
#
#
# class RangeWidget(SuffixedMultiWidget):
#     template_name = 'widgets/multiwidget.html'
#     suffixes = ['min', 'max']
#
#     def __init__(self, attrs=None):
#         widgets = (forms.TextInput, forms.TextInput)
#         super().__init__(widgets, attrs)
#
#     def decompress(self, value):
#         if value:
#             return [value.start, value.stop]
#         return [None, None]