"""Finding caregivers near a place in New York City (story #33) and filtering
them by service (#34) and availability (#35)."""

import json
from functools import lru_cache
from pathlib import Path

from django.db.models import Exists, OuterRef, Prefetch, Q

from .geocoding import distance_miles
from .models import CaregiverProfile, CaregiverService, ServiceType

NEIGHBORHOODS_FILE = Path(__file__).resolve().parent / "data" / "nyc_neighborhoods.json"

# The largest service radius a caregiver can set (see CaregiverProfile).
MAX_RADIUS_MILES = 25
# Degrees of latitude / longitude that cover MAX_RADIUS_MILES around NYC,
# used to narrow the database query before measuring exact distances.
LAT_DEGREES = MAX_RADIUS_MILES / 69.0
LNG_DEGREES = MAX_RADIUS_MILES / 52.0


@lru_cache(maxsize=1)
def neighborhoods():
    """NYC neighborhoods with a center point, sorted by borough and name."""
    with NEIGHBORHOODS_FILE.open() as f:
        return json.load(f)["neighborhoods"]


def neighborhood(code):
    """The neighborhood with this NTA code (e.g. "MN0202"), or None."""
    return next((n for n in neighborhoods() if n["code"] == code), None)


def listed_services():
    """Services a caregiver shows on search cards: active and with a price."""
    return CaregiverService.objects.filter(is_active=True, price__isnull=False)


def searchable_caregivers(viewer, available_only=True):
    """Caregivers with an account, with what the cards show.

    By default only caregivers taking new bookings are included (#35); with
    available_only=False the others are listed too, but can't be requested.
    """
    caregivers = CaregiverProfile.objects.filter(user__isnull=False)
    if available_only:
        caregivers = caregivers.filter(accepting_new_bookings=True)
    caregivers = (
        caregivers.prefetch_related(
            "supported_pet_types",
            Prefetch(
                "caregiverservice_set",
                queryset=listed_services()
                .select_related("service_type")
                .order_by("service_type__name"),
                to_attr="listed_services",
            ),
        )
        .order_by("name")
    )
    if viewer.is_authenticated:
        caregivers = caregivers.exclude(user=viewer)
    return caregivers


def caregivers_near(caregivers, latitude, longitude):
    """Caregivers whose service radius covers the point, nearest first.

    Each returned caregiver gets a `distance` attribute in miles.
    """
    latitude, longitude = float(latitude), float(longitude)
    nearby = caregivers.filter(
        latitude__range=(latitude - LAT_DEGREES, latitude + LAT_DEGREES),
        longitude__range=(longitude - LNG_DEGREES, longitude + LNG_DEGREES),
    )
    results = []
    for caregiver in nearby:
        caregiver.distance = distance_miles(
            latitude, longitude, caregiver.latitude, caregiver.longitude
        )
        if caregiver.distance <= caregiver.service_radius_miles:
            results.append(caregiver)
    results.sort(key=lambda c: (c.distance, c.name))
    return results


def caregivers_matching_text(caregivers, text):
    """Fallback when the address lookup is down: match the area by name."""
    return list(
        caregivers.filter(Q(neighborhood__icontains=text) | Q(service_area__icontains=text))
    )


def offered_service_types():
    """Service types at least one caregiver lists, for the service filter (#34)."""
    offered = listed_services().filter(
        service_type=OuterRef("pk"), caregiver__user__isnull=False
    )
    return ServiceType.objects.filter(Exists(offered)).order_by("name")


def offering_service(caregivers, service_type):
    """Caregivers who list this service as active and priced (#34)."""
    offers = listed_services().filter(
        caregiver=OuterRef("pk"), service_type=service_type
    )
    return caregivers.filter(Exists(offers))


def put_service_first(caregivers, service_type):
    """Show the filtered service first on each card."""
    for caregiver in caregivers:
        caregiver.listed_services.sort(
            key=lambda s: s.service_type_id != service_type.pk
        )
    return caregivers
