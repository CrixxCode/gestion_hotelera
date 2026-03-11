from django.db import models


class Client(models.Model):

    # Tipos de cliente según frecuencia o valor del huésped
    class ClientType(models.TextChoices):
        VIP = "VIP", "VIP"
        FREQUENT = "FRECUENTE", "Frecuente"
        REGULAR = "REGULAR", "Regular"

    # Estado actual del cliente dentro del sistema
    class ClientStatus(models.TextChoices):
        ACTIVE = "ACTIVO", "Activo"
        INACTIVE = "INACTIVO", "Inactivo"
        CURRENT_GUEST = "HUESPED_ACTUAL", "Huesped Actual"

    # ====== Datos personales del cliente ======

    # Tipo de documento (CC, Passport, etc.)
    document_type = models.CharField(max_length=40)

    # Número de documento único
    document_number = models.CharField(max_length=40, unique=True)

    # Nombres del cliente
    first_name = models.CharField(max_length=120)

    # Apellidos del cliente
    last_name = models.CharField(max_length=120)

    # Email del cliente
    email = models.EmailField(max_length=120, unique=True)

    # Teléfono del cliente
    phone = models.CharField(max_length=40, blank=True, null=True)

    # País de origen
    country = models.CharField(max_length=80, blank=True, null=True)

    # ====== Información de comportamiento del cliente ======

    # Tipo de cliente (VIP, frecuente, regular)
    client_type = models.CharField(
        max_length=20,
        choices=ClientType.choices,
        default=ClientType.REGULAR
    )

    # Contador acumulado de noches hospedadas
    # Ejemplo: 9 noches totales en el hotel
    total_stay_nights = models.PositiveIntegerField(default=0)

    # Fecha de la última estancia (normalmente la fecha de check-out)
    last_stay = models.DateField(blank=True, null=True)

    # Estado actual del cliente
    status = models.CharField(
        max_length=20,
        choices=ClientStatus.choices,
        default=ClientStatus.ACTIVE
    )

    # Fecha de creación del registro
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "client"
        ordering = ["-id"]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def resolve_client_type_by_stay_nights(self):
        nights = self.total_stay_nights or 0
        if nights >= 30:
            return self.ClientType.VIP
        if nights >= 10:
            return self.ClientType.FREQUENT
        return self.ClientType.REGULAR

    def save(self, *args, **kwargs):
        # Mantiene client_type sincronizado con las noches acumuladas.
        self.client_type = self.resolve_client_type_by_stay_nights()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name
