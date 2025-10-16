from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from accounts.views import (PasswordResetRequestView, PasswordResetConfirmView, HealthCheckView)


from accounts.views import (
    CsrfInitView, SessionLoginView, SessionLogoutView, MeSessionView,
    UserViewSet, RoleViewSet, ResourceViewSet,
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")
router.register(r"roles", RoleViewSet, basename="roles")
router.register(r"resources", ResourceViewSet, basename="resources")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),

    path("health/", HealthCheckView.as_view(), name="healthcheck"),

    path("api/auth/csrf/", CsrfInitView.as_view(), name="csrf_init"),
    path("api/auth/me/", MeSessionView.as_view(), name="session_me"),
    path("api/auth/login/", SessionLoginView.as_view(), name="session_login"),
    path("api/auth/logout/", SessionLogoutView.as_view(), name="session_logout"),
    path("api/auth/password/reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("api/auth/password/reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
]
