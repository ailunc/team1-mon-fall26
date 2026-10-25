"""Tests for the Find caregivers filters: #34 Filter Caregivers by Service and
#35 Filter Caregivers by Availability."""

from decimal import Decimal

from django.urls import reverse

from caregivers.models import CaregiverService, ServiceType
from caregivers.search import (
    offered_service_types,
    offering_service,
    searchable_caregivers,
)

from .test_search import NYU, URL, SearchTestData

BOOKING_URL = reverse("bookings:booking_create")


class FilterTestData(SearchTestData):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Chloe already walks dogs for $25 (see SearchTestData).
        cls.sitting = ServiceType.objects.get_or_create(name="Pet sitting")[0]
        cls.grooming = ServiceType.objects.get_or_create(name="Grooming")[0]
        cls.offer(cls.midtown, cls.walking, "30.00")
        cls.offer(cls.midtown, cls.sitting, "60.00")
        cls.offer(cls.lic, cls.sitting, "55.00")
        # Listed but not shown: inactive, or no price yet.
        cls.offer(cls.boerum, cls.sitting, "40.00", is_active=False)
        cls.offer(cls.staten, cls.grooming, None)
        # Not taking new bookings, but offers walks.
        cls.busy = cls.make("Busy", "40.731", "-73.995", hood="Greenwich Village",
                            accepting_new_bookings=False)
        cls.offer(cls.busy, cls.walking, "20.00")

    @classmethod
    def offer(cls, caregiver, service_type, price, is_active=True):
        return CaregiverService.objects.create(
            caregiver=caregiver, service_type=service_type,
            price=Decimal(price) if price else None, is_active=is_active,
        )


class ServiceFilterHelperTests(FilterTestData):
    def test_offered_service_types_are_listed_and_priced_ones_only(self):
        self.assertEqual(
            [st.name for st in offered_service_types()], ["Dog walking", "Pet sitting"]
        )

    def test_offering_service(self):
        caregivers = offering_service(searchable_caregivers(self.owner), self.sitting)
        self.assertEqual([c.name for c in caregivers], ["Alicia", "Marcus"])


class FilterByServiceTests(FilterTestData):
    """#34: owners pick a service and only caregivers who offer it appear."""

    def test_owner_can_see_the_service_types(self):
        response = self.client.get(URL)
        self.assertContains(response, "All services")
        self.assertContains(
            response, f'<option value="{self.walking.pk}">Dog walking</option>', html=True
        )
        self.assertContains(
            response, f'<option value="{self.sitting.pk}">Pet sitting</option>', html=True
        )
        # Nobody lists grooming with a price, so it isn't offered as a filter.
        self.assertNotContains(response, ">Grooming</option>")

    def test_only_caregivers_offering_the_service_appear(self):
        response = self.client.get(URL, {"service": self.sitting.pk})
        self.assertEqual(self.names(response), ["Alicia", "Marcus"])
        self.assertContains(response, "offering <strong>Pet sitting</strong>")

    def test_inactive_or_unpriced_services_do_not_count(self):
        response = self.client.get(URL, {"service": self.sitting.pk})
        self.assertNotIn("Priya", self.names(response))

    def test_selected_service_is_kept_in_the_form(self):
        response = self.client.get(URL, {"service": self.walking.pk})
        self.assertContains(
            response,
            f'<option value="{self.walking.pk}" selected>Dog walking</option>',
            html=True,
        )

    def test_selected_service_is_shown_first_on_the_card(self):
        response = self.client.get(URL, {"service": self.sitting.pk})
        alicia = next(c for c in response.context["caregivers"] if c.name == "Alicia")
        self.assertEqual(
            [s.service_type.name for s in alicia.listed_services],
            ["Pet sitting", "Dog walking"],
        )
        self.assertContains(response, 'class="is-match"')

    def test_owner_can_change_the_service(self):
        walking = self.client.get(URL, {"service": self.walking.pk})
        sitting = self.client.get(URL, {"service": self.sitting.pk})
        self.assertEqual(self.names(walking), ["Alicia", "Chloe"])
        self.assertEqual(self.names(sitting), ["Alicia", "Marcus"])

    def test_owner_can_remove_the_filter(self):
        response = self.client.get(URL, {"service": self.walking.pk})
        self.assertContains(response, "Clear filters")
        self.assertEqual(response.context["clear_filters_url"], URL)
        everyone = self.client.get(response.context["clear_filters_url"])
        self.assertEqual(self.names(everyone), ["Alicia", "Chloe", "Marcus", "Priya", "Sam"])
        self.assertNotContains(everyone, "Clear filters")

    def test_clearing_filters_keeps_the_location(self):
        response = self.client.get(
            URL, {"address": "x", **NYU, "service": self.walking.pk, "availability": "any"}
        )
        clear_url = response.context["clear_filters_url"]
        self.assertNotIn("service=", clear_url)
        self.assertNotIn("availability=", clear_url)
        self.assertIn("lat=40.729", clear_url)

    def test_combines_with_location_search(self):
        response = self.client.get(URL, {"address": "x", **NYU, "service": self.sitting.pk})
        self.assertEqual(self.names(response), ["Alicia", "Marcus"])
        self.assertContains(response, "2 caregivers near")
        points = [p["name"] for p in response.context["map_data"]["points"]]
        self.assertEqual(points, ["Alicia", "Marcus"])

    def test_no_match_message(self):
        response = self.client.get(
            URL, {"area": "SI0101", "service": self.sitting.pk}
        )
        self.assertEqual(self.names(response), [])
        self.assertContains(response, "No caregivers offer Pet sitting")

    def test_unknown_service_is_ignored_with_a_message(self):
        for value in ("999999", "abc", str(self.grooming.pk)):
            response = self.client.get(URL, {"service": value})
            self.assertContains(response, "Choose a service from the list.")
            self.assertEqual(len(self.names(response)), 5)

    def test_request_link_carries_the_service(self):
        response = self.client.get(URL, {"service": self.sitting.pk})
        self.assertContains(
            response,
            f"{BOOKING_URL}?caregiver={self.midtown.pk}&amp;service_type={self.sitting.pk}",
        )

    def test_booking_form_preselects_the_service(self):
        response = self.client.get(
            BOOKING_URL, {"caregiver": self.midtown.pk, "service_type": self.sitting.pk}
        )
        form = response.context["form"]
        self.assertEqual(form.initial["caregiver"], str(self.midtown.pk))
        self.assertEqual(form.initial["service_type"], str(self.sitting.pk))


class FilterByAvailabilityTests(FilterTestData):
    """#35: by default only caregivers taking new bookings are shown."""

    def test_unavailable_caregivers_are_excluded_by_default(self):
        response = self.client.get(URL)
        self.assertNotIn("Busy", self.names(response))
        self.assertContains(
            response, '<option value="available" selected>Taking new bookings</option>', html=True
        )
        self.assertNotContains(response, "Clear filters")

    def test_any_availability_includes_them_marked_unavailable(self):
        response = self.client.get(URL, {"availability": "any"})
        self.assertIn("Busy", self.names(response))
        self.assertContains(response, "Not taking new bookings")
        self.assertContains(response, "Not taking requests")
        self.assertNotContains(response, f"{BOOKING_URL}?caregiver={self.busy.pk}")
        # Available caregivers can still be requested.
        self.assertContains(response, f"{BOOKING_URL}?caregiver={self.village.pk}")

    def test_owner_can_change_availability_back(self):
        any_ = self.client.get(URL, {"availability": "any"})
        self.assertContains(any_, "Clear filters")
        available = self.client.get(URL, {"availability": "available"})
        self.assertNotIn("Busy", self.names(available))

    def test_follows_the_caregiver_setting(self):
        self.busy.accepting_new_bookings = True
        self.busy.save()
        self.assertIn("Busy", self.names(self.client.get(URL)))
        self.village.accepting_new_bookings = False
        self.village.save()
        self.assertNotIn("Chloe", self.names(self.client.get(URL)))

    def test_unknown_value_falls_back_to_available(self):
        response = self.client.get(URL, {"availability": "tomorrow"})
        self.assertNotIn("Busy", self.names(response))
        self.assertEqual(response.context["availability"], "available")

    def test_profiles_without_an_account_stay_hidden(self):
        self.make("NoAccount", "40.730", "-73.996", user=False)
        response = self.client.get(URL, {"availability": "any"})
        self.assertNotIn("NoAccount", self.names(response))

    def test_combines_with_service_and_location(self):
        params = {"address": "x", **NYU, "service": self.walking.pk}
        self.assertEqual(self.names(self.client.get(URL, params)), ["Chloe", "Alicia"])
        self.assertEqual(
            self.names(self.client.get(URL, {**params, "availability": "any"})),
            ["Chloe", "Busy", "Alicia"],
        )

    def test_unavailable_caregiver_still_cannot_be_requested(self):
        response = self.client.post(BOOKING_URL, {"caregiver": self.busy.pk})
        self.assertEqual(
            response.context["form"].errors["caregiver"],
            ["This caregiver isn't taking new bookings."],
        )
