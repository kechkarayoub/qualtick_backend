"""
Management command to logout users by blacklisting their tokens.
"""
import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.repositories import UserRepository
from accounts.utils import blacklist_user_tokens

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Management command to logout users by blacklisting their tokens.
    """
    help = 'Logout users by blacklisting their JWT tokens'
    # Ex use: python manage.py logout_users -ui 1 -f
    def add_arguments(self, parser):
        parser.add_argument(
            '-ui',
            '--user-id',
            type=int,
            help='Logout specific user by ID',
        )
        parser.add_argument(
            '-u',
            '--username',
            type=str,
            help='Logout specific user by username',
        )
        parser.add_argument(
            '-e',
            '--email',
            type=str,
            help='Logout specific user by email',
        )
        parser.add_argument(
            '-a',
            '--all-users',
            action='store_true',
            help='Logout all users',
        )
        parser.add_argument(
            '-iu',
            '--inactive-users',
            action='store_true',
            help='Logout all inactive users',
        )
        parser.add_argument(
            '-f',
            '--force',
            action='store_true',
            help='Force logout without confirmation',
        )
        parser.add_argument(
            '-as',
            '--db_alias',
            type=str,
            help='Database alias to use for logout (default: default database)',
        )
    # pylint: disable=too-many-branches
    def handle(self, *args, **options):
        User = get_user_model()
        db_alias = options['db_alias'] or None
        # Determine which users to logout
        users_to_logout = []
        if options['user_id']:
            try:
                user = UserRepository.get_by_id(options['user_id'], db_alias=db_alias)
                users_to_logout = [user]
                self.stdout.write(f"Found user: {user.username} ({user.email})")
            except User.DoesNotExist as exc:
                raise CommandError(
                    f"User with ID {options['user_id']} does not exist"
                ) from exc
        elif options['username']:
            try:
                user = UserRepository.get_by_username(username=options['username'], db_alias=db_alias)
                users_to_logout = [user]
                self.stdout.write(
                    f"Found user: {user.username} ({user.email})"
                )
            except User.DoesNotExist as exc:
                raise CommandError(
                    f"User with username '{options['username']}' does not exist"
                ) from exc
        elif options['email']:
            try:
                user = UserRepository.get_by_email(email=options['email'], db_alias=db_alias)
                users_to_logout = [user]
                self.stdout.write(f"Found user: {user.username} ({user.email})")
            except User.DoesNotExist as exc:
                raise CommandError(
                    f"User with email '{options['email']}' does not exist"
                ) from exc
        elif options['all_users']:
            users_to_logout = list(UserRepository.filter(is_active=True, db_alias=db_alias))
            self.stdout.write(f"Found {len(users_to_logout)} active users")
        elif options['inactive_users']:
            users_to_logout = list(UserRepository.filter(is_active=False, db_alias=db_alias))
            self.stdout.write(f"Found {len(users_to_logout)} inactive users")
        else:
            raise CommandError("You must specify one of: --user-id/--ui, "
                               "--username/-u, --email/-e, --all-users/-a, "
                               "or --inactive-users/-iu")
        if not users_to_logout:
            self.stdout.write(self.style.WARNING("No users found to logout"))
            return
        # Confirmation
        if not options['force']:
            if len(users_to_logout) == 1:
                confirm = input("Are you sure you want to logout user"
                                f" '{users_to_logout[0].username}'? [y/N]: ")
            else:
                confirm = input(f"Are you sure you want to logout {len(users_to_logout)}"
                                f" users? [y/N]: ")
            if confirm.lower() not in ['y', 'yes']:
                self.stdout.write("Operation cancelled")
                return
        # Logout users
        total_tokens_blacklisted = 0
        for user in users_to_logout:
            nbr_tokens_blacklisted = self.logout_user(user, db_alias=db_alias)
            total_tokens_blacklisted += nbr_tokens_blacklisted
            if nbr_tokens_blacklisted > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Logged out user '{user.username}' "
                                       f"({nbr_tokens_blacklisted} tokens blacklisted)")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"⚠ User '{user.username}' had no active tokens")
                )
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted! Total tokens blacklisted: {total_tokens_blacklisted}"
            )
        )
    def logout_user(self, user, db_alias=''):
        """
        Logout a specific user by blacklisting all their outstanding tokens.
        
        Args:
            user: User instance to logout
            db_alias: Database alias to use
            
        Returns:
            int: Number of tokens blacklisted
        """
        return blacklist_user_tokens(user, db_alias=db_alias)
