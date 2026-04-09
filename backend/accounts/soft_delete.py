from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.db.models.functions import Cast
from rest_framework import status
from rest_framework.response import Response

from accounts.models import SoftDeleteMarker


class LogicalDeleteViewSetMixin:
    """
    Enforces logical delete for API DELETE operations.
    - If model has `is_active`, DELETE sets it to False.
    - Otherwise, DELETE creates a marker in SoftDeleteMarker and hides the record in queries.
    """

    def _parse_bool(self, value) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "si", "on"}

    def _model_has_field(self, model_class, field_name: str) -> bool:
        return any(field.name == field_name for field in model_class._meta.get_fields())

    def _should_include_inactive(self) -> bool:
        request = getattr(self, "request", None)
        if not request:
            return False

        # Respect explicit filters already used by several endpoints.
        if request.query_params.get("is_active") is not None:
            return True

        return self._parse_bool(request.query_params.get("include_inactive"))

    def _should_include_deleted(self) -> bool:
        request = getattr(self, "request", None)
        if not request:
            return False
        return self._parse_bool(request.query_params.get("include_deleted"))

    def get_queryset(self):
        queryset = super().get_queryset()
        model_class = queryset.model

        if self._model_has_field(model_class, "is_active"):
            if not self._should_include_inactive():
                queryset = queryset.filter(is_active=True)
            return queryset

        if self._should_include_deleted():
            return queryset

        content_type = ContentType.objects.get_for_model(model_class)
        deleted_ids_qs = SoftDeleteMarker.objects.filter(content_type=content_type).values("object_id")

        # Works for numeric and UUID PKs by comparing casted PK to marker.object_id.
        return (
            queryset.annotate(_soft_pk=Cast("pk", output_field=models.CharField()))
            .exclude(_soft_pk__in=deleted_ids_qs)
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        model_class = instance.__class__

        if self._model_has_field(model_class, "is_active"):
            if getattr(instance, "is_active", True):
                instance.is_active = False
                instance.save(update_fields=["is_active"])
            return

        content_type = ContentType.objects.get_for_model(model_class)
        SoftDeleteMarker.objects.get_or_create(
            content_type=content_type,
            object_id=str(instance.pk),
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
