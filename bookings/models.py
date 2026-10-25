from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Booking(models.Model):
    """A pet owner's request for care from a caregiver."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Canceled"
        COMPLETED = "completed", "Completed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    pet = models.ForeignKey(
        "pets.Pet", on_delete=models.PROTECT, related_name="bookings"
    )
    caregiver = models.ForeignKey(
        "caregivers.CaregiverProfile",
        on_delete=models.PROTECT,
        related_name="booking_requests",
    )
    service_type = models.ForeignKey(
        "caregivers.ServiceType", on_delete=models.PROTECT, related_name="bookings"
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="booking_end_after_start",
            )
        ]

    def __str__(self):
        return f"Booking #{self.pk} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("bookings:booking_detail", args=[self.pk])

    @property
    def shows_pet_care_info(self):
        """Accepted and not over yet: the caregiver can see the pet's full profile."""
        return self.status == self.Status.ACCEPTED and self.end_time > timezone.now()
