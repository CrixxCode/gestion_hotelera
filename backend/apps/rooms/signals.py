from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.reservations.services import sync_room_status_for_room_ids
from .models import CleaningTask


@receiver(pre_save, sender=CleaningTask)
def cache_previous_cleaning_task_room(sender, instance, **kwargs):
    instance._previous_room_id = None

    if not instance.pk:
        return

    previous = sender.objects.filter(pk=instance.pk).values("room_id").first()
    if previous:
        instance._previous_room_id = previous["room_id"]


@receiver(post_save, sender=CleaningTask)
def sync_room_status_on_cleaning_task_save(sender, instance, **kwargs):
    sync_room_status_for_room_ids(
        [getattr(instance, "_previous_room_id", None), instance.room_id]
    )


@receiver(post_delete, sender=CleaningTask)
def sync_room_status_on_cleaning_task_delete(sender, instance, **kwargs):
    sync_room_status_for_room_ids([instance.room_id])
