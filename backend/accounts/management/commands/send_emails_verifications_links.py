"""
Management command to send email verification links to users.
"""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.core.validators import validate_email

from accounts.models import User
from accounts.services import UserService


class Command(BaseCommand):
    """
    Command to send email verification links to users.
    """
    help = """
        This command will sent verification links to emails that are not yet verified.
        Ex of execution:
            python manage.py send_emails_verifications_links
    """
    # noinspection PyMethodMayBeStatic
    def add_arguments(self, parser):
        # Parameters for the command
        parser.add_argument(
            '--email', '-e', type=str,
            help='To send verification link to a specific email address.',
        )
        parser.add_argument(
            '--db_alias', '-da', type=str,
            help='To specify the database alias to use.',
        )
    # noinspection PyMethodMayBeStatic
    def handle(self, *args, **options):
        email = options.get('email')
        db_alias = options.get('db_alias')
        self.stdout.write('Begin executing send_emails_verifications_links command.')
        if email:
            try:
                validate_email(email)
            except ValidationError:
                self.stdout.write(
                    f'Command not executed due to invalid email parameter: {email}.'
                )
                return
        result = UserService.send_emails_verifications_links(email=email, db_alias=db_alias)
        self.stdout.write(str(result))
        self.stdout.write('Ending executing send_emails_verifications_links command.')
