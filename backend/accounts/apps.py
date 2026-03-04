""" Accounts app configuration."""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    """Accounts app configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = _("Accounts")

    # noinspection PyMethodMayBeStatic
    def ready(self):
        # Import the signals
        import accounts.signals  # pylint: disable=unused-import,import-outside-toplevel
