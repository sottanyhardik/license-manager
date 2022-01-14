from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views
from .views import EBRCFetch

urlpatterns = [
    path('<int:data>/fetch/', EBRCFetch.as_view(), name='fetch_ebrc'),
    path('<int:data>/download/', views.Ebrcdump.as_view(), name='download_ebrc'),
    path('<int:data>/list/', views.EBRCList.as_view(), name='ebrc_detail_list'),
    path('', views.EBRCMain.as_view(), name='ebrc_main'),
    path('list', views.EBRCFileList.as_view(), name='ebrc_list'),
]