from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import (PasswordResetRequestView, PasswordResetConfirmView, HealthCheckView, ProfileUpdateView)

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


from accounts.views import (
    CsrfInitView, SessionLoginView, SessionLogoutView, MeSessionView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),

    path("health/", HealthCheckView.as_view(), name="healthcheck"),

    path("api/auth/csrf/", CsrfInitView.as_view(), name="csrf_init"),
    path("api/auth/me/", MeSessionView.as_view(), name="session_me"),
    path("api/auth/login/", SessionLoginView.as_view(), name="session_login"),
    path("api/auth/logout/", SessionLogoutView.as_view(), name="session_logout"),
    path("api/auth/password/reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("api/auth/password/reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("api/auth/me/update/", ProfileUpdateView.as_view(), name="profile_update"),

    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    path("api/", include("apps.clients.urls")),
    path("api/", include("apps.hotel_settings.urls")),
    path("api/", include("apps.master_data.urls")),

    path("api/", include("apps.rooms.urls"))

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
