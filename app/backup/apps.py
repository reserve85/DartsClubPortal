from django.apps import AppConfig


class BackupConfig(AppConfig):
    """Backup, restore and exports (Administration -> Import & Export)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "app.backup"
    label = "backup"
