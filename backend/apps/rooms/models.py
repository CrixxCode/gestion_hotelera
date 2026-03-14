from django.db import models
from apps.hotel_settings.models import HotelFloor

class RoomType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    capacity = models.PositiveIntegerField(default=1)
    bed_count = models.PositiveIntegerField(default=1)
    bed_type = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "room_type"
        ordering = ["name"]

    def __str__(self):
        return self.name

class Rate(models.Model):

    #relacion con el tipo de habitacion
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.CASCADE,
        related_name="rates"
    )

    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rate"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.room_type}"

class Amenity(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "amenity"
        ordering = ["name"]

    def __str__(self):
        return self.name

class Room(models.Model):
    class RoomStatus(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        OCUPADA = "OCUPADA", "Ocupada"
        MANTENIMIENTO = "MANTENIMIENTO", "Mantenimiento"
        LIMPIEZA = "LIMPIEZA", "Limpieza"
        FUERA_DE_SERVICIO = "FUERA_DE_SERVICIO", "Fuera de servicio"

    number = models.CharField(max_length=20, unique=True)

    #relacion con tipo de habitacion
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.SET_NULL,
        related_name="rooms",
        null=True,
        blank=True
    )

    #relacion con el piso
    floor = models.ForeignKey(
        HotelFloor,
        on_delete=models.CASCADE,
        related_name="rooms"
    )

    status = models.CharField(
        max_length=30,
        choices=RoomStatus.choices,
        default=RoomStatus.DISPONIBLE
    )

    notes = models.TextField(blank=True, null=True)

    amenities = models.ManyToManyField(
        Amenity,
        related_name = "room",
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "room"
        ordering = ["number"]

    def __str__(self):
        return self.number

class MaintenanceOrder(models.Model):
    class MaintenancePriority(models.TextChoices):
        BAJA = "BAJA", "Baja"
        MEDIA = "MEDIA", "Media"
        ALTA = "ALTA", "Alta"
        URGENTE = "URGENTE", "Urgente"

    class MaintenanceStatus(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        COMPLETADA = "COMPLETADA", "Completada"
        CANCELADA = "CANCELADA", "Cancelada"

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="maintenance_orders"
    )

    title = models.CharField(max_length=150)

    description = models.TextField(blank=True, null=True)

    priority = models.CharField(
        max_length=20,
        choices=MaintenancePriority.choices,
        default=MaintenancePriority.MEDIA
    )

    status = models.CharField(
        max_length=20,
        choices=MaintenanceStatus.choices,
        default=MaintenanceStatus.PENDIENTE
    )

    reported_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "maintenance_order"
        ordering = ["-reported_at"]

    def __str__(self):
        return f"{self.room.number} - {self.title}"


class CleaningTask(models.Model):
    class CleaningTaskType(models.TextChoices):
        DIARIA = "DIARIA", "Diaria"
        SALIDA = "SALIDA", "Salida"
        PROFUNDA = "PROFUNDA", "Profunda"
        INSPECCION = "INSPECCION", "Inspección"

    class CleaningStatus(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        COMPLETADA = "COMPLETADA", "Completada"

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="cleaning_tasks"
    )

    task_type = models.CharField(
        max_length=20,
        choices=CleaningTaskType.choices,
        default=CleaningTaskType.DIARIA
    )

    status = models.CharField(
        max_length=20,
        choices=CleaningStatus.choices,
        default=CleaningStatus.PENDIENTE
    )

    scheduled_for = models.DateField(blank=True, null=True)

    completed_at = models.DateTimeField(blank=True, null=True)

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cleaning_task"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.room.number} - {self.task_type}"