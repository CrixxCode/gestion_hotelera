from django.db import transaction
from rest_framework import serializers

from apps.master_data.models import MasterData
from apps.packages.models import Package
from apps.reservations.models import (
    Reservation,
    ReservationRoom,
    ReservationGuest,
    ReservationDeposit,
)
from apps.reservations.services import (
    RESERVATION_STATUS_PENDING_CODES,
    can_add_payment_to_reservation,
    find_active_rate_for_room_type_dates,
    find_overlapping_reservation_room,
    get_pending_reservation_status,
    get_reservation_financials,
    get_reservation_flow_permissions,
    get_reservation_payment_status,
    has_active_rate_for_room_type,
    is_room_status_blocked_for_reservation,
    sync_reservation_room_pricing_and_occupancy,
    validate_reservation_deposit_rules,
)
from apps.hotel_settings.models import ReservationPolicy


class ReservationPolicySummarySerializer(serializers.ModelSerializer):
    policy_type_name = serializers.CharField(source="policy_type.name", read_only=True)
    policy_type_code = serializers.CharField(source="policy_type.code", read_only=True)
    penalty_type_name = serializers.CharField(source="penalty_type.name", read_only=True)
    penalty_type_code = serializers.CharField(source="penalty_type.code", read_only=True)

    class Meta:
        model = ReservationPolicy
        fields = [
            "id",
            "hotel_settings",
            "policy_type",
            "policy_type_name",
            "policy_type_code",
            "penalty_type",
            "penalty_type_name",
            "penalty_type_code",
            "name",
            "description",
            "penalty_value",
            "hours_before_checkin",
            "is_active",
        ]
        read_only_fields = fields


def _as_serializer_error(error: Exception) -> dict:
    message_dict = getattr(error, "message_dict", None)
    if isinstance(message_dict, dict) and message_dict:
        return message_dict

    messages = getattr(error, "messages", None)
    if isinstance(messages, list) and messages:
        if len(messages) == 1:
            return {"detail": messages[0]}
        return {"detail": messages}

    return {"detail": str(error)}


class ReservationRoomSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source="room.number", read_only=True)
    room_type_name = serializers.CharField(source="room.room_type.name", read_only=True)
    room_type_capacity = serializers.IntegerField(source="room.room_type.capacity", read_only=True)
    meal_plan_name = serializers.CharField(source="meal_plan.name", read_only=True)
    meal_plan_code = serializers.CharField(source="meal_plan.code", read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = ReservationRoom
        fields = [
            "id",
            "reservation",
            "room",
            "room_number",
            "room_type_name",
            "room_type_capacity",
            "night_rate",
            "adults",
            "children",
            "meal_plan",
            "meal_plan_name",
            "meal_plan_code",
            "subtotal",
            "created_at",
        ]
        read_only_fields = ("id", "created_at", "subtotal")
        extra_kwargs = {
            "night_rate": {"required": False},
            "adults": {"required": False},
            "children": {"required": False},
        }

    def validate_night_rate(self, value):
        if value < 0:
            raise serializers.ValidationError("Night rate cannot be negative.")
        return value

    def validate_adults(self, value):
        if value < 1:
            raise serializers.ValidationError("There must be at least one adult assigned to the room.")
        return value

    def validate_children(self, value):
        if value < 0:
            raise serializers.ValidationError("Children cannot be negative.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        reservation = attrs.get("reservation", getattr(self.instance, "reservation", None))
        room = attrs.get("room", getattr(self.instance, "room", None))
        provided_night_rate = attrs.get("night_rate", None)

        should_validate_room_status = self.instance is None
        if self.instance is not None:
            if "room" in attrs and room and room.id != self.instance.room_id:
                should_validate_room_status = True
            if (
                "reservation" in attrs
                and reservation
                and reservation.id != self.instance.reservation_id
            ):
                should_validate_room_status = True

        if (
            should_validate_room_status
            and room
            and is_room_status_blocked_for_reservation(getattr(room, "status_code", None))
        ):
            status_label = room.get_status_display() or room.status_code or "estado actual"
            raise serializers.ValidationError(
                {
                    "room": (
                        f"La habitacion {room.number} no puede reservarse porque esta en {status_label.lower()}."
                    )
                }
            )

        if reservation and room:
            conflict = find_overlapping_reservation_room(
                room_id=room.id,
                expected_check_in=reservation.expected_check_in,
                expected_check_out=reservation.expected_check_out,
                exclude_reservation_room_id=getattr(self.instance, "id", None),
            )
            if conflict:
                conflict_reservation = conflict.reservation
                raise serializers.ValidationError(
                    {
                        "room": (
                            f"Room {room.number} already has an active reservation "
                            f"(#{conflict_reservation.id}) from "
                            f"{conflict_reservation.expected_check_in} to "
                            f"{conflict_reservation.expected_check_out}."
                        )
                    }
                )

        if reservation and room and reservation.package_id:
            package = reservation.package
            room_hotel_id = getattr(getattr(room, "floor", None), "hotel_settings_id", None)
            check_in = reservation.expected_check_in
            check_out = reservation.expected_check_out

            if package.start_date and check_in and check_in < package.start_date:
                raise serializers.ValidationError(
                    {"reservation": "Reservation check-in is outside the package validity period."}
                )

            if package.end_date and check_out and check_out > package.end_date:
                raise serializers.ValidationError(
                    {"reservation": "Reservation check-out is outside the package validity period."}
                )

            if room_hotel_id and package.hotel_settings_id != room_hotel_id:
                raise serializers.ValidationError(
                    {"room": "The room is not compatible with the package hotel."}
                )

            if package.room_type_id and room.room_type_id != package.room_type_id:
                raise serializers.ValidationError(
                    {"room": "The room type is not compatible with the selected package."}
                )

        if reservation and room:
            room_type_id = getattr(room, "room_type_id", None)
            if not room_type_id:
                raise serializers.ValidationError(
                    {"room": f"La habitacion {room.number} no tiene tipo de habitacion configurado."}
                )

            expected_rate = find_active_rate_for_room_type_dates(
                room_type_id=room_type_id,
                expected_check_in=reservation.expected_check_in,
                expected_check_out=reservation.expected_check_out,
            )
            has_active_rates = has_active_rate_for_room_type(room_type_id)

            if not expected_rate:
                if has_active_rates:
                    raise serializers.ValidationError(
                        {
                            "night_rate": (
                                "No existe una tarifa activa para el tipo de habitacion "
                                "en el rango de fechas de la reserva."
                            )
                        }
                    )
                raise serializers.ValidationError(
                    {
                        "night_rate": (
                            "La habitacion seleccionada no tiene una tarifa activa configurada "
                            "para su tipo de habitacion."
                        )
                    }
                )

            if provided_night_rate is not None and provided_night_rate != expected_rate.price:
                raise serializers.ValidationError(
                    {
                        "night_rate": (
                            f"La tarifa por noche debe coincidir con la tarifa activa "
                            f"({expected_rate.price}) para este tipo de habitacion."
                        )
                    }
                )

            # Siempre normalizamos la tarifa segun la configuracion activa del tipo de habitacion.
            attrs["night_rate"] = expected_rate.price

        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            instance = super().create(validated_data)
            try:
                sync_reservation_room_pricing_and_occupancy(instance.reservation)
            except Exception as exc:
                raise serializers.ValidationError(_as_serializer_error(exc))
            instance.refresh_from_db()
            return instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            updated = super().update(instance, validated_data)
            try:
                sync_reservation_room_pricing_and_occupancy(updated.reservation)
            except Exception as exc:
                raise serializers.ValidationError(_as_serializer_error(exc))
            updated.refresh_from_db()
            return updated


class ReservationGuestSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    document_type_name = serializers.CharField(source="document_type.name", read_only=True)
    document_type_code = serializers.CharField(source="document_type.code", read_only=True)

    class Meta:
        model = ReservationGuest
        fields = [
            "id",
            "reservation",
            "document_type",
            "document_type_name",
            "document_type_code",
            "document_number",
            "first_name",
            "last_name",
            "full_name",
            "birth_date",
            "nationality",
            "blood_type",
            "emergency_contact_name",
            "emergency_contact_phone",
            "created_at",
        ]
        read_only_fields = ("id", "created_at", "full_name")

    def create(self, validated_data):
        with transaction.atomic():
            instance = super().create(validated_data)
            try:
                sync_reservation_room_pricing_and_occupancy(instance.reservation)
            except Exception as exc:
                raise serializers.ValidationError(_as_serializer_error(exc))
            return instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            updated = super().update(instance, validated_data)
            try:
                sync_reservation_room_pricing_and_occupancy(updated.reservation)
            except Exception as exc:
                raise serializers.ValidationError(_as_serializer_error(exc))
            return updated


class ReservationDepositSerializer(serializers.ModelSerializer):
    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    payment_method_code = serializers.CharField(source="payment_method.code", read_only=True)
    status_name = serializers.CharField(source="status.name", read_only=True)
    status_code = serializers.CharField(source="status.code", read_only=True)

    class Meta:
        model = ReservationDeposit
        fields = [
            "id",
            "reservation",
            "deposit_date",
            "amount",
            "payment_method",
            "payment_method_name",
            "payment_method_code",
            "reference",
            "status",
            "status_name",
            "status_code",
            "notes",
            "created_at",
        ]
        read_only_fields = ("id", "created_at")

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Deposit amount must be greater than zero.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        reservation = attrs.get("reservation") or getattr(self.instance, "reservation", None)
        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        exclude_deposit_id = getattr(self.instance, "id", None)

        errors = validate_reservation_deposit_rules(
            reservation,
            amount,
            exclude_deposit_id=exclude_deposit_id,
        )
        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def create(self, validated_data):
        reservation = validated_data["reservation"]
        amount = validated_data["amount"]

        with transaction.atomic():
            locked_reservation = (
                Reservation.objects.select_related("status")
                .prefetch_related("rooms_detail", "deposits", "charges")
                .select_for_update()
                .get(pk=reservation.pk)
            )

            errors = validate_reservation_deposit_rules(locked_reservation, amount)
            if errors:
                raise serializers.ValidationError(errors)

            validated_data["reservation"] = locked_reservation
            return super().create(validated_data)

    def update(self, instance, validated_data):
        reservation = validated_data.get("reservation") or instance.reservation
        amount = validated_data.get("amount", instance.amount)
        exclude_deposit_id = instance.id

        with transaction.atomic():
            locked_reservation = (
                Reservation.objects.select_related("status")
                .prefetch_related("rooms_detail", "deposits", "charges")
                .select_for_update()
                .get(pk=reservation.pk)
            )

            errors = validate_reservation_deposit_rules(
                locked_reservation,
                amount,
                exclude_deposit_id=exclude_deposit_id,
            )
            if errors:
                raise serializers.ValidationError(errors)

            validated_data["reservation"] = locked_reservation
            return super().update(instance, validated_data)


class ReservationBusinessRulesMixin:
    def _get_business_rules(self, obj):
        if not hasattr(self, "_business_rules_cache"):
            self._business_rules_cache = {}

        cache_key = getattr(obj, "pk", None)
        if cache_key in self._business_rules_cache:
            return self._business_rules_cache[cache_key]

        financials = get_reservation_financials(obj)
        payment = get_reservation_payment_status(obj, financials=financials)
        flow = get_reservation_flow_permissions(obj)

        values = {
            "rooms_subtotal": financials["rooms_subtotal"],
            "package_subtotal": financials["package_subtotal"],
            "additional_charges_total": financials["additional_charges_total"],
            "total_deposits": financials["total_deposits"],
            "total_amount": financials["total_amount"],
            "pending_amount": financials["pending_amount"],
            "payment_status_code": payment["code"],
            "payment_status_label": payment["label"],
            "can_add_payment": can_add_payment_to_reservation(obj, financials=financials),
            **flow,
        }
        self._business_rules_cache[cache_key] = values
        return values

    def get_rooms_subtotal(self, obj):
        return self._get_business_rules(obj)["rooms_subtotal"]

    def get_package_subtotal(self, obj):
        return self._get_business_rules(obj)["package_subtotal"]

    def get_additional_charges_total(self, obj):
        return self._get_business_rules(obj)["additional_charges_total"]

    def get_total_deposits(self, obj):
        return self._get_business_rules(obj)["total_deposits"]

    def get_total_amount(self, obj):
        return self._get_business_rules(obj)["total_amount"]

    def get_pending_amount(self, obj):
        return self._get_business_rules(obj)["pending_amount"]

    def get_payment_status_code(self, obj):
        return self._get_business_rules(obj)["payment_status_code"]

    def get_payment_status_label(self, obj):
        return self._get_business_rules(obj)["payment_status_label"]

    def get_can_add_payment(self, obj):
        return self._get_business_rules(obj)["can_add_payment"]

    def get_can_confirm(self, obj):
        return self._get_business_rules(obj)["can_confirm"]

    def get_can_check_in(self, obj):
        return self._get_business_rules(obj)["can_check_in"]

    def get_can_check_out(self, obj):
        return self._get_business_rules(obj)["can_check_out"]

    def get_can_cancel(self, obj):
        return self._get_business_rules(obj)["can_cancel"]


class ReservationListSerializer(ReservationBusinessRulesMixin, serializers.ModelSerializer):
    client_full_name = serializers.CharField(source="client.full_name", read_only=True)
    client_document_number = serializers.CharField(source="client.document_number", read_only=True)
    status_name = serializers.CharField(source="status.name", read_only=True)
    status_code = serializers.CharField(source="status.code", read_only=True)
    origin_name = serializers.CharField(source="origin.name", read_only=True)
    origin_code = serializers.CharField(source="origin.code", read_only=True)
    package_catalog_name = serializers.CharField(source="package.name", read_only=True)
    package_display_name = serializers.CharField(read_only=True)
    total_rooms = serializers.IntegerField(read_only=True)
    total_guests = serializers.IntegerField(read_only=True)
    total_nights = serializers.IntegerField(read_only=True)
    policies = ReservationPolicySummarySerializer(many=True, read_only=True)
    rooms_subtotal = serializers.SerializerMethodField()
    package_subtotal = serializers.SerializerMethodField()
    additional_charges_total = serializers.SerializerMethodField()
    total_deposits = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    pending_amount = serializers.SerializerMethodField()
    payment_status_code = serializers.SerializerMethodField()
    payment_status_label = serializers.SerializerMethodField()
    can_add_payment = serializers.SerializerMethodField()
    can_confirm = serializers.SerializerMethodField()
    can_check_in = serializers.SerializerMethodField()
    can_check_out = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            "id",
            "client",
            "client_full_name",
            "client_document_number",
            "status",
            "status_name",
            "status_code",
            "origin",
            "origin_name",
            "origin_code",
            "package",
            "package_name",
            "package_catalog_name",
            "package_display_name",
            "package_price",
            "expected_check_in",
            "expected_check_out",
            "real_check_in",
            "real_check_out",
            "promo_code",
            "total_discount",
            "policies",
            "total_rooms",
            "total_guests",
            "total_nights",
            "rooms_subtotal",
            "package_subtotal",
            "additional_charges_total",
            "total_deposits",
            "total_amount",
            "pending_amount",
            "payment_status_code",
            "payment_status_label",
            "can_add_payment",
            "can_confirm",
            "can_check_in",
            "can_check_out",
            "can_cancel",
            "created_by",
            "created_at",
        ]
        read_only_fields = (
            "id",
            "client_full_name",
            "client_document_number",
            "status_name",
            "status_code",
            "origin_name",
            "origin_code",
            "package_name",
            "package_catalog_name",
            "package_display_name",
            "package_price",
            "total_rooms",
            "total_guests",
            "total_nights",
            "rooms_subtotal",
            "package_subtotal",
            "additional_charges_total",
            "total_deposits",
            "total_amount",
            "pending_amount",
            "payment_status_code",
            "payment_status_label",
            "can_add_payment",
            "can_confirm",
            "can_check_in",
            "can_check_out",
            "can_cancel",
            "created_at",
        )


class ReservationDetailSerializer(ReservationBusinessRulesMixin, serializers.ModelSerializer):
    client_full_name = serializers.CharField(source="client.full_name", read_only=True)
    client_document_number = serializers.CharField(source="client.document_number", read_only=True)
    client_email = serializers.EmailField(source="client.email", read_only=True)
    client_phone = serializers.CharField(source="client.phone", read_only=True)

    status_name = serializers.CharField(source="status.name", read_only=True)
    status_code = serializers.CharField(source="status.code", read_only=True)
    origin_name = serializers.CharField(source="origin.name", read_only=True)
    origin_code = serializers.CharField(source="origin.code", read_only=True)
    package_catalog_name = serializers.CharField(source="package.name", read_only=True)
    package_display_name = serializers.CharField(read_only=True)

    rooms_detail = ReservationRoomSerializer(many=True, read_only=True)
    guests = ReservationGuestSerializer(many=True, read_only=True)
    deposits = ReservationDepositSerializer(many=True, read_only=True)
    policies = ReservationPolicySummarySerializer(many=True, read_only=True)

    total_rooms = serializers.IntegerField(read_only=True)
    total_guests = serializers.IntegerField(read_only=True)
    total_nights = serializers.IntegerField(read_only=True)
    rooms_subtotal = serializers.SerializerMethodField()
    package_subtotal = serializers.SerializerMethodField()
    additional_charges_total = serializers.SerializerMethodField()
    total_deposits = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    pending_amount = serializers.SerializerMethodField()
    payment_status_code = serializers.SerializerMethodField()
    payment_status_label = serializers.SerializerMethodField()
    can_add_payment = serializers.SerializerMethodField()
    can_confirm = serializers.SerializerMethodField()
    can_check_in = serializers.SerializerMethodField()
    can_check_out = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            "id",
            "client",
            "client_full_name",
            "client_document_number",
            "client_email",
            "client_phone",
            "status",
            "status_name",
            "status_code",
            "origin",
            "origin_name",
            "origin_code",
            "package",
            "package_name",
            "package_catalog_name",
            "package_display_name",
            "package_price",
            "expected_check_in",
            "expected_check_out",
            "real_check_in",
            "real_check_out",
            "promo_code",
            "total_discount",
            "notes",
            "policies",
            "total_rooms",
            "total_guests",
            "total_nights",
            "rooms_subtotal",
            "package_subtotal",
            "additional_charges_total",
            "total_deposits",
            "total_amount",
            "pending_amount",
            "payment_status_code",
            "payment_status_label",
            "can_add_payment",
            "can_confirm",
            "can_check_in",
            "can_check_out",
            "can_cancel",
            "rooms_detail",
            "guests",
            "deposits",
            "created_by",
            "created_at",
        ]
        read_only_fields = (
            "id",
            "client_full_name",
            "client_document_number",
            "client_email",
            "client_phone",
            "status_name",
            "status_code",
            "origin_name",
            "origin_code",
            "package_name",
            "package_catalog_name",
            "package_display_name",
            "package_price",
            "total_rooms",
            "total_guests",
            "total_nights",
            "rooms_subtotal",
            "package_subtotal",
            "additional_charges_total",
            "total_deposits",
            "total_amount",
            "pending_amount",
            "payment_status_code",
            "payment_status_label",
            "can_add_payment",
            "can_confirm",
            "can_check_in",
            "can_check_out",
            "can_cancel",
            "policies",
            "rooms_detail",
            "guests",
            "deposits",
            "created_at",
        )


class ReservationWriteSerializer(serializers.ModelSerializer):
    package = serializers.PrimaryKeyRelatedField(
        queryset=Package.objects.all(),
        required=False,
        allow_null=True,
    )
    policies = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=ReservationPolicy.objects.filter(is_active=True),
        required=False,
    )

    class Meta:
        model = Reservation
        fields = [
            "id",
            "client",
            "status",
            "origin",
            "package",
            "package_name",
            "package_price",
            "policies",
            "expected_check_in",
            "expected_check_out",
            "real_check_in",
            "real_check_out",
            "promo_code",
            "total_discount",
            "notes",
            "created_by",
            "created_at",
        ]
        read_only_fields = (
            "id",
            "created_at",
            "status",
            "real_check_in",
            "real_check_out",
            "package_name",
            "package_price",
        )

    def validate_package(self, value):
        if value and not value.is_active:
            raise serializers.ValidationError("The selected package is inactive.")
        return value

    @staticmethod
    def _validate_package_dates(package, check_in, check_out):
        if not package:
            return None

        if package.start_date and check_in and check_in < package.start_date:
            return "The selected package is not available for the expected check-in date."

        if package.end_date and check_out and check_out > package.end_date:
            return "The selected package is not available for the expected check-out date."

        return None

    @staticmethod
    def _build_package_snapshot(package):
        if not package:
            return {
                "package_name": "",
                "package_price": 0,
            }

        return {
            "package_name": package.name,
            "package_price": package.base_price,
        }

    def validate(self, attrs):
        attrs.pop("status", None)
        attrs.pop("real_check_in", None)
        attrs.pop("real_check_out", None)

        expected_check_in = attrs.get(
            "expected_check_in",
            getattr(self.instance, "expected_check_in", None),
        )
        expected_check_out = attrs.get(
            "expected_check_out",
            getattr(self.instance, "expected_check_out", None),
        )
        real_check_in = attrs.get(
            "real_check_in",
            getattr(self.instance, "real_check_in", None),
        )
        real_check_out = attrs.get(
            "real_check_out",
            getattr(self.instance, "real_check_out", None),
        )
        total_discount = attrs.get(
            "total_discount",
            getattr(self.instance, "total_discount", 0),
        )
        package = attrs.get("package", getattr(self.instance, "package", None))

        errors = {}

        if expected_check_in and expected_check_out:
            if expected_check_out <= expected_check_in:
                errors["expected_check_out"] = "Expected check-out must be later than expected check-in."

        if real_check_out and not real_check_in:
            errors["real_check_out"] = "Real check-out cannot be registered without a real check-in."

        if real_check_in and real_check_out and real_check_out < real_check_in:
            errors["real_check_out"] = "Real check-out cannot be earlier than real check-in."

        if total_discount is not None and total_discount < 0:
            errors["total_discount"] = "Total discount cannot be negative."

        package_date_error = self._validate_package_dates(
            package,
            expected_check_in,
            expected_check_out,
        )
        if package_date_error:
            errors["package"] = package_date_error

        if self.instance and expected_check_in and expected_check_out:
            room_conflicts = []
            reservation_rooms = self.instance.rooms_detail.select_related("room", "room__floor").all()
            for reservation_room in reservation_rooms:
                conflict = find_overlapping_reservation_room(
                    room_id=reservation_room.room_id,
                    expected_check_in=expected_check_in,
                    expected_check_out=expected_check_out,
                    exclude_reservation_id=self.instance.id,
                )
                if conflict:
                    conflict_reservation = conflict.reservation
                    room_conflicts.append(
                        (
                            f"Room {reservation_room.room.number} conflicts with reservation "
                            f"#{conflict_reservation.id} "
                            f"({conflict_reservation.expected_check_in} to "
                            f"{conflict_reservation.expected_check_out})."
                        )
                    )

            if room_conflicts:
                errors["rooms_detail"] = room_conflicts

            if package:
                package_conflicts = []
                for reservation_room in reservation_rooms:
                    room = reservation_room.room
                    room_hotel_id = getattr(getattr(room, "floor", None), "hotel_settings_id", None)

                    if room_hotel_id and package.hotel_settings_id != room_hotel_id:
                        package_conflicts.append(
                            f"Room {room.number} belongs to a different hotel than the selected package."
                        )
                        continue

                    if package.room_type_id and room.room_type_id != package.room_type_id:
                        package_conflicts.append(
                            f"Room {room.number} is not compatible with package room type '{package.room_type.name}'."
                        )

                if package_conflicts:
                    errors["package"] = package_conflicts

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def create(self, validated_data):
        policies = validated_data.pop("policies", None)
        package = validated_data.get("package")
        validated_data.pop("status", None)
        validated_data["real_check_in"] = None
        validated_data["real_check_out"] = None
        validated_data.update(self._build_package_snapshot(package))

        pending_status = get_pending_reservation_status()
        if not pending_status:
            expected_codes = ", ".join(RESERVATION_STATUS_PENDING_CODES)
            raise serializers.ValidationError(
                {
                    "status": (
                        f"No existe un estado activo de pendiente ({expected_codes}) "
                        f"en {MasterData.Group.RESERVATION_STATUS}."
                    )
                }
            )

        validated_data["status"] = pending_status
        reservation = super().create(validated_data)

        if policies is not None:
            reservation.policies.set(policies)

        return reservation

    def update(self, instance, validated_data):
        policies = validated_data.pop("policies", None)
        validated_data.pop("status", None)
        validated_data.pop("real_check_in", None)
        validated_data.pop("real_check_out", None)

        if "package" in validated_data:
            package = validated_data.get("package")
            validated_data.update(self._build_package_snapshot(package))

        reservation = super().update(instance, validated_data)

        if policies is not None:
            reservation.policies.set(policies)

        return reservation
