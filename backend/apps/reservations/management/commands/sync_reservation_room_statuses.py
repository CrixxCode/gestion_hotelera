from django.core.management.base import BaseCommand

from apps.reservations.services import sync_all_room_statuses


class Command(BaseCommand):
    help = (
        "Sincroniza estados de habitaciones segun reservas activas y hora de check-in. "
        "Pensado para ejecucion periodica (cron / Task Scheduler / Celery beat)."
    )

    def handle(self, *args, **options):
        # Este comando permite recalcular estados por paso del tiempo,
        # incluso cuando no hubo eventos de guardado en reservas/habitaciones.
        processed, changed = sync_all_room_statuses()
        self.stdout.write(
            self.style.SUCCESS(
                f"Sync completed. Rooms processed: {processed}. Rooms updated: {changed}."
            )
        )
