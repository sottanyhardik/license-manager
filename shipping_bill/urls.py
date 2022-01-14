from django.urls import path

from . import views

urlpatterns = [
    path('<int:data>/dgft/fetch/', views.ShippingDGFTBillFetchView.as_view(), name='fetch_dgft_shipping_bill'),
    path('<int:data>/fetch/', views.ShippingBillFetchView.as_view(), name='fetch_shipping_bill'),
    path('<int:data>/download/', views.ShippingBillDumpView.as_view(), name='download_shipping_bill'),
    path('<int:data>/list/', views.ShippingBillList.as_view(), name='shipping_bill_detail_list'),
 ]