from typing import Iterable
from rest_framework.permissions import BasePermission

def _require_scopes(user, required: Iterable[str]) -> bool:
    if not user or not user.is_authenticated:
        return False
    user_scopes = user.resource_keys()
    return all(scope in user_scopes for scope in required)

class HasResourceScopes(BasePermission):
    """
    Usa en la vista: required_scopes = ["users.read"]
    """
    def has_permission(self, request, view):
        required = getattr(view, "required_scopes", [])
        if not required:
            # Si una vista no define required_scopes, por defecto exige autenticación.
            return bool(request.user and request.user.is_authenticated)
        return _require_scopes(request.user, required)

def require_scopes(*scopes: str):
    """
    Decorador para FBV o para asignar dinámicamente en CBV.
    """
    def wrapper(view_cls_or_func):
        setattr(view_cls_or_func, "required_scopes", list(scopes))
        return view_cls_or_func
    return wrapper
