from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class EloConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.elo"
    label = "elo"
    verbose_name = _("Elo ranking")
