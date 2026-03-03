from rest_framework.permissions import BasePermission
from accounts.models import Resource


class HasResourcePermission(BasePermission):
    """
    1) Si el view define required_scopes (ej: ["users.read"]), valida contra Resource.key del usuario.
    2) Si NO define required_scopes, hace fallback a la validación por link_backend (compatibilidad).
    """

    def has_permission(self, request, view):
        user = request.user

        # Usuario autenticado
        if not user or not user.is_authenticated:
            return False

        # Superusuario: acceso total
        if getattr(user, "is_superuser", False):
            return True

        # 1) Validación por Resource.key (recomendado)
        required = getattr(view, "required_scopes", None)

        # Si el view tiene método para resolver scopes dinámicos, úsalo
        if hasattr(view, "get_required_scopes") and callable(getattr(view, "get_required_scopes")):
            try:
                required = view.get_required_scopes()
            except Exception:
                pass

        if required:
            user_keys = user.resource_keys()
            # Estricto: debe tener TODOS los scopes requeridos
            return all(scope in user_keys for scope in required)

        # 2) Fallback por link_backend (tu lógica actual)
        path = (request.path or "").strip().lower()
        if not path.endswith("/"):
            path += "/"

        user_resources = Resource.objects.filter(roles__users=user).distinct()

        for resource in user_resources:
            link = (resource.link_backend or "").strip().lower()
            if not link:
                continue
            if not link.endswith("/"):
                link += "/"
            if path.startswith(link):
                return True

        return False