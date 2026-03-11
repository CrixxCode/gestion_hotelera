from rest_framework.routers import DefaultRouter
from .views import HotelSettingsViewSet, HotelFloorViewSet

router = DefaultRouter()
router.register(r"hotel-settings", HotelSettingsViewSet, basename="hotel-settings")
router.register(r"hotel-floors", HotelFloorViewSet, basename="hotel-floors")

urlpatterns = router.urls