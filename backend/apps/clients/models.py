from django.db import models

from apps.master_data.models import MasterData


class Client(models.Model):
    # Personal data
    document_type = models.ForeignKey(
        MasterData,
        on_delete=models.PROTECT,
        related_name="clients_document_type",
        limit_choices_to={"group": MasterData.Group.DOCUMENT_TYPE},
    )
    document_number = models.CharField(max_length=40, unique=True)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    email = models.EmailField(max_length=120, unique=True)
    phone = models.CharField(max_length=40, blank=True, null=True)
    country = models.CharField(max_length=80, blank=True, null=True)

    # Behavioral data
    client_type = models.ForeignKey(
        MasterData,
        on_delete=models.PROTECT,
        related_name="clients_type",
        limit_choices_to={"group": MasterData.Group.CLIENT_TYPE},
    )
    total_stay_nights = models.PositiveIntegerField(default=0)
    last_stay = models.DateField(blank=True, null=True)
    status = models.ForeignKey(
        MasterData,
        on_delete=models.PROTECT,
        related_name="clients_status",
        limit_choices_to={"group": MasterData.Group.CLIENT_STATUS},
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "client"
        ordering = ["-id"]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def document_type_code(self):
        return self.document_type.code if self.document_type else None

    @property
    def client_type_code(self):
        return self.client_type.code if self.client_type else None

    @property
    def status_code(self):
        return self.status.code if self.status else None

    def resolve_client_type_code_by_stay_nights(self):
        nights = self.total_stay_nights or 0
        if nights >= 30:
            return "VIP"
        if nights >= 10:
            return "FRECUENTE"
        return "REGULAR"

    def save(self, *args, **kwargs):
        # Keep client_type synchronized with accumulated nights.
        auto_client_type_code = self.resolve_client_type_code_by_stay_nights()
        auto_client_type = MasterData.objects.filter(
            group=MasterData.Group.CLIENT_TYPE,
            code=auto_client_type_code,
        ).first()

        if auto_client_type:
            self.client_type = auto_client_type

        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name
