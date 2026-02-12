from django.db import models


class ScreeningLog(models.Model):
    """Stores a lightweight audit trail of screening searches for dashboards/stats."""

    query = models.CharField(max_length=512)
    matches_found = models.PositiveIntegerField(default=0)
    high_risk_matches = models.PositiveIntegerField(default=0)
    min_score_threshold = models.PositiveIntegerField(default=90)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.query} ({self.matches_found})"
