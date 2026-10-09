from rest_framework import serializers


class OrderLineInput(serializers.Serializer):
    offering_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=20)
    expected_version = serializers.IntegerField(min_value=1)
    expected_price_paise = serializers.IntegerField(min_value=0)
    option_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    notes = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")

    def validate_option_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Each option can be selected only once.")
        return value


class OrderInput(serializers.Serializer):
    lines = OrderLineInput(many=True)

    def validate_lines(self, value):
        if not 1 <= len(value) <= 20:
            raise serializers.ValidationError("An order needs 1 to 20 lines.")
        return value


class ServiceRequestInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["WAITER", "BILL"])


class StaffLoginInput(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class ProgressInput(serializers.Serializer):
    to_state = serializers.ChoiceField(choices=["PREPARING", "READY", "SERVED", "CANCELLED"])
    from_state = serializers.ChoiceField(choices=["QUEUED", "PREPARING", "READY"], required=False)
    quantity = serializers.IntegerField(min_value=1)
    expected_revision = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")

    def validate(self, attrs):
        if attrs["to_state"] == "CANCELLED" and "from_state" not in attrs:
            raise serializers.ValidationError({"from_state": "Specify which unserved state to cancel."})
        return attrs


class BillingInput(serializers.Serializer):
    external_bill_ref = serializers.CharField(max_length=200)
    external_total_paise = serializers.IntegerField(min_value=0)
    payment_method_label = serializers.CharField(max_length=100)


class BrandUpdateInput(serializers.Serializer):
    display_name = serializers.CharField(max_length=120, required=False)
    short_name = serializers.CharField(max_length=80, allow_blank=True, required=False)
    primary_color = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$", required=False)
    accent_color = serializers.RegexField(r"^#[0-9A-Fa-f]{6}$", required=False)
    support_email = serializers.EmailField(allow_blank=True, required=False)
    support_phone = serializers.CharField(max_length=40, allow_blank=True, required=False)
    logo_asset_id = serializers.UUIDField(allow_null=True, required=False)
    icon_asset_id = serializers.UUIDField(allow_null=True, required=False)
    hero_asset_id = serializers.UUIDField(allow_null=True, required=False)


class OutletBrandInput(BrandUpdateInput):
    pass


class OutletOrderingInput(serializers.Serializer):
    ordering_enabled = serializers.BooleanField(required=False)
    delay_message = serializers.CharField(max_length=300, allow_blank=True, allow_null=True, required=False)


class CategoryInput(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    display_order = serializers.IntegerField(required=False, default=0)


class ItemInput(serializers.Serializer):
    category_id = serializers.UUIDField()
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(allow_blank=True, required=False, default="")
    dietary_type = serializers.ChoiceField(choices=["UNSPECIFIED", "VEGETARIAN", "VEGAN", "NON_VEGETARIAN"],
                                          required=False, default="UNSPECIFIED")
    allergens = serializers.ListField(child=serializers.CharField(max_length=100), required=False, default=list)


class QuickItemInput(ItemInput):
    price_paise = serializers.IntegerField(min_value=0)
    estimate_max_minutes = serializers.IntegerField(min_value=0, required=False, default=25)


class VariantInput(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    display_order = serializers.IntegerField(required=False, default=0)


class OfferingInput(serializers.Serializer):
    variant_id = serializers.UUIDField()
    price_paise = serializers.IntegerField(min_value=0)
    estimate_min_minutes = serializers.IntegerField(min_value=0, required=False, default=0)
    estimate_max_minutes = serializers.IntegerField(min_value=0)
    available = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        if attrs["estimate_max_minutes"] < attrs["estimate_min_minutes"]:
            raise serializers.ValidationError("Maximum estimate must be at least the minimum.")
        return attrs


class OfferingUpdateInput(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    price_paise = serializers.IntegerField(min_value=0, required=False)
    estimate_min_minutes = serializers.IntegerField(min_value=0, required=False)
    estimate_max_minutes = serializers.IntegerField(min_value=0, required=False)
    available = serializers.BooleanField(required=False)
    active = serializers.BooleanField(required=False)


class TableInput(serializers.Serializer):
    label = serializers.CharField(max_length=80)


class ModifierGroupInput(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    min_choices = serializers.IntegerField(min_value=0, required=False, default=0)
    max_choices = serializers.IntegerField(min_value=0, required=False, default=1)
    display_order = serializers.IntegerField(required=False, default=0)

    def validate(self, attrs):
        if attrs["max_choices"] < attrs["min_choices"]:
            raise serializers.ValidationError("Maximum choices must be at least the minimum.")
        return attrs


class ModifierOptionInput(serializers.Serializer):
    name = serializers.CharField(max_length=120)


class OutletModifierInput(serializers.Serializer):
    option_id = serializers.UUIDField()
    price_delta_paise = serializers.IntegerField(min_value=0, required=False, default=0)
    available = serializers.BooleanField(required=False, default=True)
