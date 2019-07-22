from django.urls import path

from . import views

urlpatterns = [
    # ex: /polls/
    path('add/', views.LicenseDetailCreateView.as_view(), name='add-license'),
    path('list/', views.LicenseDetailListView.as_view(), name='list-license'),
    path('<int:pk>/', views.LicenseDetailView.as_view(), name='license-detail'),
    path('<int:pk>/update', views.LicenseDetailUpdateView.as_view(), name='license-update'),
    path('<int:pk>/pdf', views.PDFLicenseDetailView.as_view(), name='license-pdf')
    # # ex: /polls/5/
    # path('<int:question_id>/', views.detail, name='detail'),
    # # ex: /polls/5/results/
    # path('<int:question_id>/results/', views.results, name='results'),
    # # ex: /polls/5/vote/
    # path('<int:question_id>/vote/', views.vote, name='vote'),
]