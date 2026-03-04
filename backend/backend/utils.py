# pylint: disable=logging-fstring-interpolation,logging-fstring-interpolation
"""Utility functions for the backend application."""

import json
import logging
import os
import random
import string
from zoneinfo import available_timezones, ZoneInfo

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connection, connections
from django.utils.timezone import localtime, now
from django.utils.translation import gettext_lazy as _


# Get a logger instance
logger = logging.getLogger(__name__)


def execute_native_query(query, query_name="query", is_get=True, db_alias=''):
    """
    Execute a native query.
    :param query: (str) The query to execute.
    :param query_name: (str) The query description.
    :param is_get: (bool) True if query will get data else False.
    :param db_alias: (str) The database alias to use.
    :return: None if is_get is False else the rows result.
    """
    with (connections[db_alias] if db_alias else connection).cursor() as cursor:
        # Remove return lines and double spaces from query.
        query = query.replace("\n", " ").replace("    ", " ").replace("    ",
            " ").replace("   ", " ").replace("   ", " ").replace("  ", " ").replace("  ",
            " ")
        # Log the query
        logger.info(query_name)
        logger.info(query)
        # Execute the query
        cursor.execute(query)
        # if is_get query: return rows result. Else return None
        if is_get:
            rows = cursor.fetchall()
            return rows
        return None


def generate_random_code(nbr_digit=6):
    """
    Generate a nbr_digit code code.
    :param nbr_digit:
    :return: generated code
    """
    if nbr_digit <= 0:
        return ""
    min_number = 10 ** (nbr_digit - 1)
    max_number = 10 ** nbr_digit - 1
    return f"{random.randint(min_number, max_number)}"


def generate_random_string(length=10):
    """
    Generate a random string.
    :param length:
    :return: generated string
    """
    characters = string.ascii_letters + string.digits  # a-z, A-Z, 0-9
    return ''.join(random.choice(characters) for _ in range(length))


def get_all_timezones(as_list=False):
    """
    Get all available timezones.
    :param as_list: (bool) If True, return as list of lists else list of tuples.
    :return: list of tuples or list of lists
    """
    all_timezones = available_timezones()
    default_value = ["", _("Select")]
    all_timezones_list = [default_value]
    if as_list:
        all_timezones_list.extend(
            [[timezone, timezone] for timezone in sorted(all_timezones)])
        return all_timezones_list
    all_timezones_list = [tuple(default_value)]
    all_timezones_list.extend(
        [(timezone, timezone) for timezone in sorted(all_timezones)])
    return all_timezones_list


def get_geolocation_info(client_ip, fields="country,countryCode"):
    """
    Fetch geolocation data from ip-api.com.
    Args:
        client_ip (str): The IP address to lookup.
        fields (str): Comma-separated fields (e.g., "country,countryCode,city").
    Returns:
        dict: Raw API response (e.g., {"country": "France", "countryCode": "FR"}).
    """
    try:
        response = requests.get(f"http://ip-api.com/json/{client_ip}",
                                params={"fields": fields}, timeout=5,)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"ip-api.com request failed: {str(e)}")
        return {"status": "fail", "message": str(e)}


def get_local_datetime(datetime_to_localize, custom_timezone):
    """
    Convert a UTC time to the user's local time based on their timezone.
    :param datetime_to_localize: The datetime to localize.
    :param custom_timezone: The timezone to convert to.
    :return: The datetime object in the custom timezone.
    """
    timezone_object = ZoneInfo(custom_timezone)
    return localtime(datetime_to_localize, timezone=timezone_object)


def get_db_alias(request=None, user=None):
    """
    Determine the database alias to use based on the request.
    Args:
        request (HttpRequest): The incoming HTTP request object (optional).
        user (User): The user object (optional).
    Returns:
        str: The database alias to use.
    """
    if request and hasattr(request, 'db_alias'):
        return request.db_alias
    if user and hasattr(user, 'db_alias'):
        return user.db_alias
    return ''


def get_email_base_context(selected_language="fr"):
    """
    Generate common email's context dictionary.
    Args:
        selected_language (str): The current language to handle direction in email.
    Returns:
        Dict: A dictionary that contains common params used in emails.
    """
    context = {
        'company_address': settings.COMPANY_ADDRESS,
        'app_name': settings.APPLICATION_NAME,
        'current_year': now().year,
        'direction': "rtl" if selected_language == "ar" else "ltr",
        'from_email': settings.DEFAULT_FROM_EMAIL,
        'frontend_endpoint': settings.FRONTEND_ENDPOINT,
    }
    return context


PHONE_NUMBER_VERIFICATION_METHOD = [
    ("", _("Select")), ("apple", _("Apple")), ("default", _("Default")),
    ("facebook", _("Facebook")), ("google", _("Google")),
    ("sms", _("Sms")), ("yahoo", _("Yahoo")), ("whatsapp", _("Whatsapp")), ("x", _("X")),
]


def remove_file(request, file_url):
    """
    Removes a file from the storage based on the provided file URL.
    Args:
        request (Request): The incoming HTTP request object.
        file_url (str): The URL of the file to be deleted.
            This URL is used to derive the file's path in storage.
    Returns:
        None: This function performs the deletion and does not return any value.
    """
    # Convert the file URL to a relative file path
    relative_path = file_url.replace(request.build_absolute_uri(settings.MEDIA_URL), "")
    # Construct the full path of the file in the storage directory
    file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    # Attempt to delete the file if it exists in the local filesystem
    if os.path.exists(file_path):
        os.remove(file_path)
    elif default_storage.exists(relative_path):
        # If the file is stored remotely (e.g., in cloud storage), delete it there
        default_storage.delete(relative_path)


def send_phone_message(content, receivers_numbers, as_sms=False, handle_error=False,
                       do_not_mock_api=False):
    """
    Send content to receivers_numbers.
    :param content: (str) text content.
    :param receivers_numbers: (list) List of phone numbers receivers.
    :param as_sms: (bool) By default we sent content by whatsapp, if as_sms is true,
        we sent it as sms.
    :param handle_error: (bool) To handle error for testing purpose.
    :param do_not_mock_api: (bool) Flag to run api for even if it is for testing.
    :return: function execution
    """
    if as_sms:
        return send_sms(sms_content=content, receivers_numbers=receivers_numbers,
                        do_not_mock_api=do_not_mock_api)
    return send_whatsapp(whatsapp_content=content, receivers_numbers=receivers_numbers,
                         handle_error=handle_error, do_not_mock_api=do_not_mock_api)


def send_sms(sms_content, receivers_numbers, handle_error=False, do_not_mock_api=False):
    """
    Send sms_content to receivers_numbers.
    :param sms_content: (str) SMS text content.
    :param receivers_numbers: (list) List of phone numbers receivers.
    :param do_not_mock_api: (bool) Flag to run api even if it is for testing.
    :return: response_data: (dict) A dictionary that contains nbr_verification_codes_sent
        and all_verification_codes_sent
    """
    if settings.ENVIRONMENT == "development":
        logger.info(f"sms_content: {sms_content}")
        logger.info(f"receivers_numbers: {receivers_numbers}")
    else:
        pass
    response_data = {
        'nbr_verification_codes_sent': 0,
    }
    if settings.TEST and do_not_mock_api is False:
        response_data = {
            'nbr_verification_codes_sent': len(receivers_numbers),
            'all_verification_codes_sent': True,
        }
        if handle_error:
            response_data = {
                'nbr_verification_codes_sent': 0,
                'all_verification_codes_sent': False,
            }
        return response_data
    return response_data


def send_whatsapp(whatsapp_content, receivers_numbers, handle_error=False,
                  do_not_mock_api=False):
    """
    Send sms_content to receivers_numbers.
    :param whatsapp_content: (str) SMS text content.
    :param receivers_numbers: (list) List of phone numbers receivers.
    :param handle_error: (bool) To handle error for testing purpose.
    :return: response_data: (dict) A dictionary that contains nbr_verification_codes_sent
        and all_verification_codes_sent
    :param do_not_mock_api: (bool) Flag to run api even if it is for testing.
    """
    if settings.ENVIRONMENT == "development":
        logger.info(f"whatsapp_content: {whatsapp_content}")
        logger.info(f"receivers_numbers: {receivers_numbers}")
    else:
        pass
    response_data = {
        'nbr_verification_codes_sent': 0,
    }
    if settings.TEST and do_not_mock_api is False:
        response_data = {
            'nbr_verification_codes_sent': len(receivers_numbers),
            'all_verification_codes_sent': True,
        }
        if handle_error:
            response_data = {
                'nbr_verification_codes_sent': 0,
                'all_verification_codes_sent': False,
            }
        return response_data
    url = settings.WHATSAPP_INSTANCE_URL
    for receiver_number in receivers_numbers:
        headers = {
            "accept": "application/json",
            'content-type': 'application/json',
            "authorization": f"Bearer {settings.WHATSAPP_INSTANCE_TOKEN}"
        }
        data = {"chatId": f"{receiver_number.replace('+', '')}@c.us",
                "message": whatsapp_content}
        if handle_error:
            data = {}
        response = requests.request("POST", url, json=data, headers=headers, timeout=5)
        if response.status_code == 200:
            json_content = json.loads(response.content)
            if json_content.get('status') == 'success':
                response_data['nbr_verification_codes_sent'] += 1
            else:
                logger.error(response.text)
        else:
            logger.error(response.text)
    # Checking if all receivers_numbers receive the whatsapp content
    response_data['all_verification_codes_sent'] = response_data['nbr_verification_codes_sent'] == len(receivers_numbers) # pylint: disable=line-too-long
    return response_data


def upload_file(request, file, directory, prefix=""):
    """
    Uploads a file and returns the URL and file path.

    Args:
        request (Request): The incoming HTTP request object.
        file (UploadedFile): The file object to be uploaded.
        directory (String): Directory where to set files.
        prefix (String) (Optional): The prefix to add before the file name.

    Returns:
        tuple: A tuple containing the URL of the uploaded file and the saved file path.
            Example: ("/media/profile_images/profile_image.jpg", "/path/to/file")
    """
    if file:
        # Define the file path for saving the uploaded file
        file_path = os.path.join(directory, f'{prefix}{file.name}')
        # Save the file to the default storage location
        saved_path = default_storage.save(file_path, ContentFile(file.read()))
        # Construct the full URL for accessing the uploaded file
        file_url = f"{request.build_absolute_uri(settings.MEDIA_URL)}{saved_path}"
    else:
        # If no file is provided, return None for both URL and path
        file_url = None
        file_path = None
    return file_url, file_path
