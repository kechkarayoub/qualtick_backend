"""Accounts custom middlwares"""
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils.timezone import activate


class TimezoneMiddleware:  # pylint: disable=too-few-public-methods
    """
        Middleware to activate the timezone for each request based on the authenticated
         user's preference.
        Defaults to settings.TIME_ZONE for unauthenticated users or if the user's 
        timezone is invalid.
    """
    def __init__(self, get_response):
        """
            Initializes the middleware.
            :param get_response: The next middleware or view in the request-response cycle.
        """
        self.get_response = get_response
    def __call__(self, request):
        """
            Process each request to set the appropriate timezone.
            :param request: The current HTTP request object.
            :return: The response object after processing the request.
        """
        if request.user.is_authenticated:
            user_timezone = request.user.get_user_timezone()
            try:
                # Use ZoneInfo for the user's timezone
                activate(ZoneInfo(user_timezone))
            except KeyError:
                # Fallback to settings.TIME_ZONE if the timezone is invalid
                activate(ZoneInfo(settings.TIME_ZONE))
        else:
            # Default to settings.TIME_ZONE for unauthenticated users
            activate(ZoneInfo(settings.TIME_ZONE))
        # Pass the request to the next middleware or view.
        return self.get_response(request)
