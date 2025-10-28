from rest_framework.permissions import BasePermission
from accounts.models import Resource


class HasResourceLinkPermission(BasePermission):
    """
    Verifica acceso según el link_backend de un recurso.
    Se concede acceso si la ruta solicitada (request.path)
    comienza con el link_backend de un Resource asociado a
    algún rol del usuario autenticado.
    Incluye depuración para ver qué rutas y recursos compara.
    """

    def has_permission(self, request, view):
        user = request.user

        # 1️⃣ Usuario autenticado
        if not user or not user.is_authenticated:
            print("🚫 Usuario no autenticado.")
            return False

        # 2️⃣ Superusuario: acceso total
        if getattr(user, "is_superuser", False):
            print(f"✅ Superusuario '{user.username}' con acceso total.")
            return True

        # 3️⃣ Normaliza ruta del request
        path = (request.path or "").strip().lower()
        if not path.endswith("/"):
            path += "/"

        # 4️⃣ Recursos del usuario
        user_resources = Resource.objects.filter(roles__users=user).distinct()

        # 5️⃣ Imprimir depuración
        print(f"👤 Usuario autenticado: {user.username}")
        print(f"📡 Ruta solicitada: {path}")
        print(f"🎯 Recursos asociados: {list(user_resources.values_list('link_backend', flat=True))}")

        # 6️⃣ Verifica coincidencias
        for resource in user_resources:
            link = (resource.link_backend or "").strip().lower()
            if not link:
                continue
            if not link.endswith("/"):
                link += "/"

            if path.startswith(link):
                print(f"✅ Acceso concedido: {path} coincide con {link}")
                return True

        print(f"❌ Acceso denegado para '{user.username}' en {path}")
        return False
