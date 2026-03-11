from django.db import models


class DailyAPICounter(models.Model):
    """Tracks daily Google Places API usage to enforce the free-tier budget."""
    date = models.DateField(unique=True)
    count = models.IntegerField(default=0)

    class Meta:
        app_label = "mysite"

    def __str__(self):
        return f"{self.date}: {self.count} calls"
