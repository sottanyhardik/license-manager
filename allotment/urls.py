from django.contrib.auth.decorators import login_required
from django.urls import path
from . import views

urlpatterns = [
    # ex: /polls/
    path('add/', login_required(views.AllotmentCreateView.as_view()), name='allotment-add'),
    path('card/<int:pk>/', login_required(views.CardView.as_view()), name='allotment-card'),
    path('<int:pk>', login_required(views.StartAllotmentView.as_view()), name='allotment-details'),
    path('', login_required(views.AllotmentView.as_view()), name='allotment-list'),
    path('<int:pk>/update', login_required(views.AllotmentUpdateView.as_view()), name='allotment-update'),
    path('<int:pk>/delete', login_required(views.AllotmentDeleteView.as_view()), name='allotment-delete'),
    path('<int:pk>/item/delete', login_required(views.AllotmentDeleteItemsView.as_view()), name='allotment-item-delete'),
    path('<int:pk>/verify', login_required(views.AllotmentVerifyView.as_view()), name='allotment-verify'),
    path('<int:pk>/data/', login_required(views.allotment_data), name='allotment-data'),
    path('<int:pk>/download/', login_required(views.SendAllotmentView.as_view()), name='allotment-download'),
    path('download/', login_required(views.DownloadPendingAllotmentView.as_view()), name='allotment-pending'),
    path('<int:pk>/generate/', login_required(views.ARODocumentGenerateView.as_view()), name='allotment-generate-aro'),
    path('<int:pk>/tl/', login_required(views.GenerateTransferLetterView.as_view()), name='allotment-tl')
]