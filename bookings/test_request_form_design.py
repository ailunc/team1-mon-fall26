"""The Request care form as designed in Figma ("Send Booking Request"):
numbered steps, pet cards, only the chosen caregiver's services, and a
back link to the caregiver's profile (story #38)."""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from caregivers.models import CaregiverProfile, CaregiverService

from .forms import BookingRequestForm
from .tests import BookingTestData

CREATE_URL = reverse("bookings:booking_create")


class RequestFormDesignTests(BookingTestData):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        CaregiverService.objects.create(
            caregiver=cls.caregiver, service_type=cls.walk, price=Decimal("20")
        )
        CaregiverService.objects.create(
            caregiver=cls.caregiver, service_type=cls.sitting, price=Decimal("40"),
            is_active=False,
        )
        cls.other = CaregiverProfile.objects.create(
            name="Walker Mask", service_area="Gowanus",
            user=get_user_model().objects.create_user("walker", password="pw-12345!"),
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def test_steps_are_numbered_in_the_design_order(self):
        response = self.client.get(CREATE_URL)
        content = response.content.decode()
        positions = [
            content.index(f'step-number step-{n}" aria-hidden="true">{n}</span> {label}')
            for n, label in ((1, "Caregiver"), (2, "Which pet"), (3, "Service"), (4, "When"))
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertContains(response, "Note for the caregiver")
        self.assertContains(response, 'placeholder="Anything specific about this visit"')

    def test_pets_are_shown_as_cards(self):
        response = self.client.get(CREATE_URL)
        self.assertContains(response, 'class="pet-option theme-dog"')
        self.assertContains(response, "<strong>Biscuit</strong>")
        self.assertContains(response, "<span>Dog</span>")

    def test_only_active_services_of_each_caregiver_are_offered(self):
        response = self.client.get(CREATE_URL)
        offers = json.loads(
            response.content.decode()
            .split('<script id="caregiver-services" type="application/json">')[1]
            .split("</script>")[0]
        )
        self.assertEqual(offers, {str(self.caregiver.pk): [self.walk.pk]})
        # Each service chip says which service it is, so the page can hide the rest.
        self.assertContains(response, f'data-service="{self.walk.pk}"')

    def test_caregiver_services_helper(self):
        form = BookingRequestForm(owner=self.owner)
        self.assertEqual(form.caregiver_services(), {self.caregiver.pk: [self.walk.pk]})

    def test_back_link_returns_to_the_caregiver_profile(self):
        response = self.client.get(CREATE_URL, {"caregiver": self.caregiver.pk})
        self.assertContains(response, "Back to caregiver profile")
        self.assertContains(response, reverse("caregiver", args=[self.caregiver.pk]))

    def test_back_link_defaults_to_my_requests(self):
        response = self.client.get(CREATE_URL)
        self.assertContains(response, "Back to my requests")
        self.assertIsNone(response.context["back_caregiver"])

    def test_service_not_offered_is_still_rejected(self):
        response = self.client.post(
            CREATE_URL, self.form_data(service_type=self.sitting.pk)
        )
        self.assertContains(response, "This caregiver doesn&#x27;t offer that service.")
