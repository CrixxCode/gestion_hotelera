"""
Management command: seed_rbac
==============================
Crea (o actualiza) los Resources, Roles y el superusuario demo.

Uso:
    python manage.py seed_rbac                  # seed completo
    python manage.py seed_rbac --only-resources # solo crea/actualiza resources
    python manage.py seed_rbac --assign-admin   # asigna rol admin a todos los superusuarios

Los fields de cada Resource:
  key           → identificador de permiso  (ej: "users.read")
  name          → etiqueta en el menú
  icon          → clase CSS del ícono (PrimeIcons → "pi pi-xxx")
  link          → ruta Angular (ej: "/usuarios")
  link_backend  → ruta API (ej: "/api/users/")
  is_menu       → ¿aparece en el menú lateral?
  order         → posición en el menú (menor = primero)
  parent_key    → key del resource padre (para sub-menús), None = raíz
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Role, Resource

User = get_user_model()

# ──────────────────────────────────────────────────────────────────────────────
# RESOURCES
# Tupla: (key, name, icon, link, link_backend, is_menu, order, parent_key)
# ──────────────────────────────────────────────────────────────────────────────
RESOURCES = [
    # ── Dashboard ────────────────────────────────────────────────────────────
    (
        "dashboard.view",
        "Dashboard",
        "pi pi-home",
        "/dashboard",
        "",
        True,
        1,
        None,
    ),
    # ── Usuarios ─────────────────────────────────────────────────────────────
    (
        "users.read",
        "Usuarios",
        "pi pi-users",
        "/usuarios",
        "/api/users/",
        True,
        2,
        None,
    ),
    (
        "users.write",
        "Gestionar usuarios",
        "",
        "",
        "/api/users/",
        False,   # no aparece en menú; es sólo un permiso
        0,
        None,
    ),
    # ── Roles ─────────────────────────────────────────────────────────────────
    (
        "roles.read",
        "Roles",
        "pi pi-shield",
        "/roles",
        "/api/roles/",
        True,
        3,
        None,
    ),
    (
        "roles.write",
        "Gestionar roles",
        "",
        "",
        "/api/roles/",
        False,
        0,
        None,
    ),
    # ── Recursos ──────────────────────────────────────────────────────────────
    (
        "resources.read",
        "Recursos",
        "pi pi-list",
        "/recursos",
        "/api/resources/",
        True,
        4,
        None,
    ),
    (
        "resources.write",
        "Gestionar recursos",
        "",
        "",
        "/api/resources/",
        False,
        0,
        None,
    ),
    # ── Perfil / contraseña ───────────────────────────────────────────────────
    (
        "auth.password.change",
        "Cambiar contraseña",
        "pi pi-key",
        "",
        "/api/auth/password/change/",
        False,
        0,
        None,
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# ROLES  →  { slug: [list of resource keys] }
# ──────────────────────────────────────────────────────────────────────────────
ROLES = {
    "admin": {
        "name": "Administrador",
        "description": "Acceso total al sistema.",
        "keys": [
            "dashboard.view",
            "users.read",
            "users.write",
            "roles.read",
            "roles.write",
            "resources.read",
            "resources.write",
            "auth.password.change",
        ],
    },
    "manager": {
        "name": "Gerente",
        "description": "Acceso de lectura y gestión básica.",
        "keys": [
            "dashboard.view",
            "users.read",
            "roles.read",
            "resources.read",
            "auth.password.change",
        ],
    },
    "staff": {
        "name": "Personal",
        "description": "Acceso básico al sistema.",
        "keys": [
            "dashboard.view",
            "auth.password.change",
        ],
    },
}


class Command(BaseCommand):
    help = "Crea o actualiza Resources, Roles y el superusuario demo del sistema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-resources",
            action="store_true",
            help="Solo crea/actualiza los Resources (no toca roles ni usuarios).",
        )
        parser.add_argument(
            "--assign-admin",
            action="store_true",
            help="Asigna el rol 'admin' a todos los superusuarios existentes.",
        )

    # ──────────────────────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("\n🌱  Iniciando seed RBAC...\n"))

        self._seed_resources()

        if not options["only_resources"]:
            self._seed_roles()
            self._seed_superuser()

        if options["assign_admin"]:
            self._assign_admin_to_superusers()

        self.stdout.write(self.style.SUCCESS("\n✅  Seed RBAC completado.\n"))

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _seed_resources(self):
        self.stdout.write("  📦  Creando / actualizando Resources...")

        # Índice por key para resolver parent_key
        created_map: dict[str, Resource] = {}

        for key, name, icon, link, link_backend, is_menu, order, parent_key in RESOURCES:
            parent = created_map.get(parent_key) if parent_key else None

            obj, created = Resource.objects.update_or_create(
                key=key,
                defaults={
                    "name": name,
                    "icon": icon,
                    "link": link,
                    "link_backend": link_backend,
                    "is_menu": is_menu,
                    "order": order,
                    "parent": parent,
                },
            )
            created_map[key] = obj
            verb = "CREADO  " if created else "actualizado"
            self.stdout.write(f"      {verb} → {key}")

    def _seed_roles(self):
        self.stdout.write("  🛡️   Creando / actualizando Roles...")

        for slug, data in ROLES.items():
            role, created = Role.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                },
            )
            resources = list(Resource.objects.filter(key__in=data["keys"]))
            role.resources.set(resources)

            verb = "CREADO  " if created else "actualizado"
            self.stdout.write(
                f"      {verb} → {slug}  ({len(resources)} recursos asignados)"
            )

    def _seed_superuser(self):
        self.stdout.write("  👤  Verificando superusuario demo...")

        if not User.objects.filter(username="admin").exists():
            admin_user = User.objects.create_superuser(
                username="admin",
                email="admin@hotel.local",
                password="admin12345",
            )
            admin_role = Role.objects.filter(slug="admin").first()
            if admin_role:
                admin_user.roles.add(admin_role)
            self.stdout.write(
                self.style.SUCCESS(
                    "      ✔  Superusuario creado → admin / admin12345"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "      ⚠️  ¡Cambia la contraseña en producción!"
                )
            )
        else:
            # Si ya existe, asegúrate de que tenga el rol admin
            existing = User.objects.get(username="admin")
            admin_role = Role.objects.filter(slug="admin").first()
            if admin_role and not existing.roles.filter(slug="admin").exists():
                existing.roles.add(admin_role)
                self.stdout.write(
                    "      ✔  Rol 'admin' asignado al superusuario existente."
                )
            else:
                self.stdout.write("      ─  Superusuario 'admin' ya existe y tiene su rol.")

    def _assign_admin_to_superusers(self):
        self.stdout.write("  🔑  Asignando rol 'admin' a todos los superusuarios...")
        admin_role = Role.objects.filter(slug="admin").first()
        if not admin_role:
            self.stdout.write(
                self.style.ERROR("      ✗  Rol 'admin' no encontrado. Ejecuta el seed completo primero.")
            )
            return

        superusers = User.objects.filter(is_superuser=True)
        count = 0
        for user in superusers:
            if not user.roles.filter(slug="admin").exists():
                user.roles.add(admin_role)
                count += 1
                self.stdout.write(f"      ✔  {user.username}")

        if count == 0:
            self.stdout.write("      ─  Todos los superusuarios ya tenían el rol 'admin'.")
        else:
            self.stdout.write(self.style.SUCCESS(f"      ✔  {count} superusuario(s) actualizado(s)."))
