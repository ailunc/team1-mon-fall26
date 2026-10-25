from django import forms
from django.utils import timezone

from caregivers.models import CaregiverProfile, CaregiverService, ServiceType
from pets.models import Pet

from .models import Booking

DATETIME_FORMAT = "%Y-%m-%dT%H:%M"


def offered_service_type_ids(caregiver):
    """IDs of the service types a caregiver currently offers."""
    return set(
        CaregiverService.objects.filter(
            caregiver=caregiver, is_active=True
        ).values_list("service_type_id", flat=True)
    )


class BookingRequestForm(forms.ModelForm):
    """Lets a signed-in owner request care for one of their own pets."""

    pet = forms.ModelChoiceField(
        queryset=Pet.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
        label="Which pet needs care?",
        error_messages={
            "required": "Choose one of your pets.",
            "invalid_choice": "Choose one of your pets.",
        },
    )
    caregiver = forms.ModelChoiceField(
        queryset=CaregiverProfile.objects.none(),
        empty_label="Choose a caregiver",
        label="Caregiver",
        error_messages={
            "required": "Choose a caregiver.",
            "invalid_choice": "This caregiver isn't taking new bookings.",
        },
    )
    service_type = forms.ModelChoiceField(
        queryset=ServiceType.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
        label="Service",
        error_messages={
            "required": "Choose a service.",
            "invalid_choice": "Choose a service.",
        },
    )

    class Meta:
        model = Booking
        fields = ["pet", "caregiver", "service_type", "start_time", "end_time", "notes"]
        labels = {
            "start_time": "Starts",
            "end_time": "Ends",
            "notes": "Anything the caregiver should know?",
        }
        error_messages = {
            "start_time": {"required": "Choose when care should start."},
            "end_time": {"required": "Choose when care should end."},
        }
        widgets = {
            "start_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format=DATETIME_FORMAT
            ),
            "end_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format=DATETIME_FORMAT
            ),
            "notes": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Anything specific about this visit",
                }
            ),
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pet"].queryset = Pet.objects.filter(owner=owner).select_related(
            "pet_type"
        )
        # Owners can't send a request to their own caregiver profile.
        self.fields["caregiver"].queryset = (
            CaregiverProfile.objects.filter(accepting_new_bookings=True)
            .exclude(user=owner)
            .order_by("name")
        )
        self.fields["service_type"].queryset = ServiceType.objects.order_by("name")

        # Readable choice labels without touching the other apps' models.
        self.fields["pet"].label_from_instance = lambda pet: pet.name
        self.fields["caregiver"].label_from_instance = (
            lambda cg: f"{cg.name} · {cg.service_area}" if cg.service_area else cg.name
        )
        self.fields["service_type"].label_from_instance = lambda st: st.name
        for name in ("start_time", "end_time"):
            self.fields[name].input_formats = [DATETIME_FORMAT]

    def caregiver_services(self):
        """{caregiver id: [service type ids]} for the caregivers on the form.

        The page uses it to show only the chosen caregiver's services.
        """
        offers = {}
        rows = CaregiverService.objects.filter(
            is_active=True, caregiver__in=self.fields["caregiver"].queryset
        ).values_list("caregiver_id", "service_type_id")
        for caregiver_id, service_type_id in rows:
            offers.setdefault(caregiver_id, []).append(service_type_id)
        return offers

    def clean_start_time(self):
        start = self.cleaned_data["start_time"]
        if start <= timezone.now():
            raise forms.ValidationError("Start time must be in the future.")
        return start

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and end <= start:
            self.add_error("end_time", "End time must be after the start time.")

        caregiver = cleaned.get("caregiver")
        service_type = cleaned.get("service_type")
        if caregiver and service_type:
            offered = offered_service_type_ids(caregiver)
            # Only enforce once the caregiver has listed their services.
            if offered and service_type.pk not in offered:
                self.add_error(
                    "service_type", "This caregiver doesn't offer that service."
                )
        return cleaned
