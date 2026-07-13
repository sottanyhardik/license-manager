from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
for viewset, endpoint, basename in views.MASTER_VIEWSETS:
    router.register(endpoint, viewset, basename=basename)
router.register("changes", views.MasterChangeViewSet, basename="masterchange")

urlpatterns = router.urls
