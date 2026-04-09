import uuid
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        default='avatars/default-avatar.png',
    )

    def resource_keys(self) -> set[str]:
        """
        Conjunto de Resource.key agregados por roles del usuario.
        """
        keys_qs = (
            Resource.objects.filter(
                is_active=True,
                roleresource__is_active=True,
                roleresource__role__is_active=True,
                roleresource__role__userrole__user=self,
                roleresource__role__userrole__is_active=True,
            )
            .exclude(key__isnull=True)
            .exclude(key__exact="")
            .values_list("key", flat=True)
            .distinct()
        )
        return set(keys_qs)


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    users = models.ManyToManyField("User", related_name="roles", through="UserRole")

    def __str__(self):
        return self.name


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # RBAC
    key = models.CharField(max_length=120, unique=True)  # p.ej. "users.read"
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # Enlaces
    link = models.CharField(blank=True)         # ruta FRONTEND (Angular) ej: "/reservas"
    link_backend = models.CharField(blank=True) # ruta BACKEND (API) ej: "/api/reservas/"

    # CAMPOS PARA MENÚ DINÁMICO
    icon = models.CharField(max_length=160, blank=True)  # ej: "fa-solid fa-calendar w-5"
    order = models.PositiveIntegerField(default=0)       # orden en el menú
    is_menu = models.BooleanField(default=True)          # si se muestra en el aside
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE
    )

    roles = models.ManyToManyField("Role", related_name="resources", through="RoleResource")

    def __str__(self):
        return self.key


class UserRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "role")


class RoleResource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("role", "resource")


class SoftDeleteMarker(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("content_type", "object_id")
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]
