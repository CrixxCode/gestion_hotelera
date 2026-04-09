import logging

from rest_framework.permissions import BasePermission

from accounts.models import Resource

logger = logging.getLogger(__name__)


class HasResourcePermission(BasePermission):
    """
    1) If the view defines required_scopes (for example: ["users.read"]),
       validate against the user's Resource.key set.
    2) If the view does not define required_scopes, fallback to link_backend
       path matching for backward compatibility.
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if getattr(user, "is_superuser", False):
            return True

        required = getattr(view, "required_scopes", None)

        if hasattr(view, "get_required_scopes") and callable(getattr(view, "get_required_scopes")):
            try:
                required = view.get_required_scopes()
            except Exception:
                logger.exception("Error resolving required scopes in %s", view.__class__.__name__)
                return False

        if required:
            user_keys = user.resource_keys()
            return all(scope in user_keys for scope in required)

        path = (request.path or "").strip().lower()
        if not path.endswith("/"):
            path += "/"

        user_resources = Resource.objects.filter(
            is_active=True,
            roleresource__is_active=True,
            roleresource__role__is_active=True,
            roleresource__role__userrole__user=user,
            roleresource__role__userrole__is_active=True,
        ).distinct()

        for resource in user_resources:
            link = (resource.link_backend or "").strip().lower()
            if not link:
                continue
            if not link.endswith("/"):
                link += "/"
            if path.startswith(link):
                return True

        return False
