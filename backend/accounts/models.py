import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        default='avatars/default-avatar.png',  # fallback para usuarios sin avatar
    )
    # Campos extra si se requieren en el futuro
    # ejemplo: phone = models.CharField(max_length=20, blank=True)

    def resource_keys(self) -> set[str]:
        """
        Conjunto de resource.key agregados por roles del usuario.
        """
        keys = set()
        for role in self.roles.all().prefetch_related("resources"):
            keys.update(role.resources.values_list("key", flat=True))
        return keys


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)

    users = models.ManyToManyField("User", related_name="roles", through="UserRole")

    def __str__(self):
        return self.name


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=120, unique=True)  # p.ej. "users.read"
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    roles = models.ManyToManyField("Role", related_name="resources", through="RoleResource")

    def __str__(self):
        return self.key


class UserRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "role")


class RoleResource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("role", "resource")
