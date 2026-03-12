# pylint: disable=protected-access,too-many-instance-attributes
"""
Comprehensive test suite for backend models.

This module provides tests for:
- ContactMessage model functionality
- ContactMessageInternationalization model functionality
- ContactMessageQuerySet functionality
- ContactMessagePerformance
- ContactMessageAdmin functionality
"""

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpRequest
from django.test import TestCase
from django.utils.translation import activate, gettext_lazy as _
from django.utils import timezone as django_timezone

from accounts.repositories.user_repository import UserRepository
from backend.admin import ContactMessageAdmin
from backend.models import ContactMessage
from backend.repositories.contact_message_repository import ContactMessageRepository
from backend.utils import get_db_alias

User = get_user_model()


class ContactMessageModelTest(TestCase):
    """Test cases for ContactMessage model."""

    def setUp(self):
        """Set up test data."""
        db_alias = get_db_alias()
        from uuid import uuid4
        suffix = uuid4().hex[:8]
        self.user = UserRepository.create_user(
            username=f'testuser_{suffix}',
            email=f'testuser_{suffix}@example.com',
            password='testpassword123',
            current_language='en',
            db_alias=db_alias
        )
        self.valid_contact_data = {
            'name': 'John Doe',
            'email': 'john.doe@example.com',
            'subject': 'support',
            'message': 'This is a test message with sufficient length to pass validation.',
            'user': self.user
        }
        activate(self.user.current_language)

    def test_contact_message_creation_success(self):
        """Test successful creation of ContactMessage."""
        db_alias = get_db_alias()
        contact = ContactMessageRepository.create(db_alias=db_alias,
                                                  **self.valid_contact_data)
        self.assertEqual(contact.name, 'John Doe')
        self.assertEqual(contact.email, 'john.doe@example.com')
        self.assertEqual(contact.subject, 'support')
        self.assertEqual(contact.message,
                'This is a test message with sufficient length to pass validation.')
        self.assertEqual(contact.user, self.user)
        self.assertEqual(contact.status, 'new')  # Default status
        self.assertIsNotNone(contact.created_at)
        self.assertIsNotNone(contact.updated_at)
        self.assertEqual(contact.admin_notes, '')

    def test_contact_message_creation_without_user(self):
        """Test creation of ContactMessage without associated user."""
        db_alias = get_db_alias()
        data = self.valid_contact_data.copy()
        del data['user']
        contact = ContactMessageRepository.create(db_alias=db_alias, **data)
        self.assertEqual(contact.name, 'John Doe')
        self.assertEqual(contact.email, 'john.doe@example.com')
        self.assertIsNone(contact.user)
        self.assertEqual(contact.status, 'new')

    def test_contact_message_str_representation(self):
        """Test the string representation of ContactMessage."""
        db_alias = get_db_alias()
        contact = ContactMessageRepository.create(db_alias=db_alias,
                                                  **self.valid_contact_data)
        expected_str = f"John Doe - Technical Support ({contact.created_at.strftime(
            '%Y-%m-%d')})"
        self.assertEqual(str(contact), expected_str)

    def test_contact_message_subject_choices(self):
        """Test all subject choices work correctly."""
        db_alias = get_db_alias()
        subject_choices = ['support', 'billing', 'feature', 'partnership', 'other']
        for subject in subject_choices:
            data = self.valid_contact_data.copy()
            data['subject'] = subject
            data['email'] = f'{subject}@example.com'  # Make email unique
            contact = ContactMessageRepository.create(db_alias=db_alias, **data)
            self.assertEqual(contact.subject, subject)

    def test_contact_message_status_choices(self):
        """Test all status choices work correctly."""
        status_choices = ['new', 'in_progress', 'resolved', 'closed']
        db_alias = get_db_alias()
        for status in status_choices:
            data = self.valid_contact_data.copy()
            data['status'] = status
            data['email'] = f'{status}@example.com'  # Make email unique
            contact = ContactMessageRepository.create(db_alias=db_alias, **data)
            self.assertEqual(contact.status, status)

    def test_contact_message_message_length_validation(self):
        """Test message length validation (minimum 10 characters)."""
        data = self.valid_contact_data.copy()
        data['message'] = 'Too short'  # Only 9 characters
        contact = ContactMessage(**data)
        with self.assertRaises(ValidationError):
            contact.full_clean()

    def test_contact_message_name_max_length(self):
        """Test name field maximum length validation."""
        data = self.valid_contact_data.copy()
        data['name'] = 'x' * 101  # Exceeds max_length of 100
        contact = ContactMessage(**data)
        with self.assertRaises(ValidationError):
            contact.full_clean()

    def test_contact_message_email_validation(self):
        """Test email field validation."""
        data = self.valid_contact_data.copy()
        data['email'] = 'invalid-email-format'
        contact = ContactMessage(**data)
        with self.assertRaises(ValidationError):
            contact.full_clean()

    def test_contact_message_invalid_subject_choice(self):
        """Test that invalid subject choice raises validation error."""
        data = self.valid_contact_data.copy()
        data['subject'] = 'invalid_subject'
        contact = ContactMessage(**data)
        with self.assertRaises(ValidationError):
            contact.full_clean()

    def test_contact_message_invalid_status_choice(self):
        """Test that invalid status choice raises validation error."""
        data = self.valid_contact_data.copy()
        data['status'] = 'invalid_status'
        contact = ContactMessage(**data)
        with self.assertRaises(ValidationError):
            contact.full_clean()

    def test_contact_message_auto_timestamps(self):
        """Test that created_at and updated_at are automatically set."""
        db_alias = get_db_alias()
        contact = ContactMessageRepository.create(db_alias=db_alias, **self.valid_contact_data)
        # Check that timestamps are set
        self.assertIsNotNone(contact.created_at)
        self.assertIsNotNone(contact.updated_at)
        # Initially, created_at and updated_at should be very close
        time_diff = abs((contact.updated_at - contact.created_at).total_seconds())
        self.assertLess(time_diff, 1)  # Less than 1 second difference
        # Update the contact and check that updated_at changes
        original_updated_at = contact.updated_at
        contact.admin_notes = 'Updated notes'
        contact.save(using=db_alias or None)
        contact.refresh_from_db(using=db_alias or None)
        self.assertGreater(contact.updated_at, original_updated_at)

    def test_contact_message_user_foreign_key_cascade(self):
        """Test that deleting a user sets the contact message user to NULL."""
        db_alias = get_db_alias()
        contact = ContactMessageRepository.create(db_alias=db_alias, **self.valid_contact_data)
        # Verify the user is associated
        self.assertEqual(contact.user, self.user)
        # Delete the user
        self.user.delete()
        # Refresh the contact message and check user is set to NULL
        contact.refresh_from_db(using=db_alias or None)
        self.assertIsNone(contact.user)

    def test_contact_message_ordering(self):
        """Test that contact messages are ordered by created_at descending."""
        db_alias = get_db_alias()
        # Create multiple contact messages
        contact1 = ContactMessageRepository.create(
            db_alias=db_alias,
            name='First Contact',
            email='first@example.com',
            subject='support',
            message='First message with sufficient length for validation.'
        )
        contact2 = ContactMessageRepository.create(
            db_alias=db_alias,
            name='Second Contact',
            email='second@example.com',
            subject='billing',
            message='Second message with sufficient length for validation.'
        )
        contact3 = ContactMessageRepository.create(
            db_alias=db_alias,
            name='Third Contact',
            email='third@example.com',
            subject='feature',
            message='Third message with sufficient length for validation.'
        )
        # Get all contacts in default order
        contacts = list(ContactMessageRepository.all(db_alias=db_alias))
        # Should be ordered by created_at descending (newest first)
        self.assertEqual(contacts[0], contact3)
        self.assertEqual(contacts[1], contact2)
        self.assertEqual(contacts[2], contact1)

    def test_contact_message_meta_attributes(self):
        """Test model meta attributes."""
        meta = ContactMessage._meta
        self.assertEqual(meta.db_table, 'backend_contact_message')
        self.assertEqual(meta.ordering, ['-created_at'])
        self.assertEqual(str(meta.verbose_name), 'Contact Message')
        self.assertEqual(str(meta.verbose_name_plural), 'Contact Messages')

    def test_contact_message_indexes(self):
        """Test that proper indexes are created."""
        meta = ContactMessage._meta
        index_fields = []
        for index in meta.indexes:
            index_fields.extend(index.fields)
        expected_indexed_fields = ['status', 'subject', 'created_at', 'email']
        for field in expected_indexed_fields:
            self.assertIn(field, index_fields)

    def test_get_subject_display_translated(self):
        """Test the get_subject_display_translated method."""
        db_alias = get_db_alias()
        contact = ContactMessageRepository.create(db_alias=db_alias, **self.valid_contact_data)
        # Test with different subjects
        subject_translations = {
            'support': 'Technical Support',
            'billing': 'Billing & Account',
            'feature': 'Feature Request',
            'partnership': 'Partnership',
            'other': 'Other'
        }
        for subject, expected_display in subject_translations.items():
            contact.subject = subject
            contact.save(using=db_alias or None)
            display = contact.get_subject_display_translated()
            self.assertEqual(str(display), expected_display)

    def test_get_status_display_translated(self):
        """Test the get_status_display_translated method."""
        db_alias = get_db_alias()
        contact = ContactMessageRepository.create(db_alias=db_alias, **self.valid_contact_data)
        # Test with different statuses
        status_translations = {
            'new': 'New',
            'in_progress': 'In Progress',
            'resolved': 'Resolved',
            'closed': 'Closed'
        }
        for status, expected_display in status_translations.items():
            contact.status = status
            contact.save(using=db_alias or None)
            display = contact.get_status_display_translated()
            self.assertEqual(str(display), expected_display)

    def test_contact_message_admin_notes_optional(self):
        """Test that admin_notes field is optional."""
        data = self.valid_contact_data.copy()
        # Test without admin_notes
        db_alias = get_db_alias()
        contact = ContactMessageRepository.create(db_alias=db_alias, **data)
        self.assertEqual(contact.admin_notes, '')
        # Test with admin_notes
        data['admin_notes'] = 'This is an admin note for internal use.'
        contact_with_notes = ContactMessageRepository.create(
            db_alias=db_alias,
            name='Jane Doe',
            email='jane.doe@example.com',
            subject='billing',
            message='Another test message with sufficient length.',
            admin_notes='This is an admin note for internal use.'
        )
        self.assertEqual(contact_with_notes.admin_notes,
                         'This is an admin note for internal use.')

    def test_contact_message_field_help_texts(self):
        """Test that all fields have proper help texts."""
        contact = ContactMessage()
        expected_help_texts = {
            'name': 'The full name of the person contacting us',
            'email': 'Email address for response',
            'subject': 'Category of the inquiry',
            'message': 'The detailed message from the user',
            'status': 'Current status of the message',
            'created_at': 'When the message was submitted',
            'updated_at': 'When the message was last updated',
            'user': 'Associated user account if logged in',
            'admin_notes': 'Internal notes for administrators'
        }
        for field_name, expected_help_text in expected_help_texts.items():
            field = contact._meta.get_field(field_name)
            self.assertEqual(str(field.help_text), expected_help_text)

    def test_contact_message_field_verbose_names(self):
        """Test that all fields have proper verbose names."""
        contact = ContactMessage()
        expected_verbose_names = {
            'name': 'Full Name',
            'email': 'Email Address',
            'subject': 'Subject',
            'message': 'Message',
            'status': 'Status',
            'created_at': 'Created At',
            'updated_at': 'Updated At',
            'user': 'User',
            'admin_notes': 'Admin Notes'
        }
        for field_name, expected_verbose_name in expected_verbose_names.items():
            field = contact._meta.get_field(field_name)
            self.assertEqual(str(field.verbose_name), expected_verbose_name)


class ContactMessageInternationalizationTest(TestCase):
    """Test cases for ContactMessage internationalization features."""

    def setUp(self):
        """Set up test data."""
        self.contact_data = {
            'name': 'John Doe',
            'email': 'john.doe@example.com',
            'subject': 'support',
            'message': 'This is a test message with sufficient length to pass validation.'
        }

    def test_contact_message_field_translations(self):
        """Test that field labels are properly translated."""
        # Test with English (default)
        activate('en')
        contact = ContactMessage(**self.contact_data)
        # Check that gettext_lazy objects are properly handled
        name_field = contact._meta.get_field('name')
        self.assertEqual(str(name_field.verbose_name), 'Full Name')
        subject_field = contact._meta.get_field('subject')
        self.assertEqual(str(subject_field.verbose_name), 'Subject')

    def test_subject_choices_translations(self):
        """Test that subject choices support translation."""
        db_alias = get_db_alias()
        _contact = ContactMessageRepository.create(db_alias=db_alias, **self.contact_data)
        # The choices should use gettext_lazy for translation
        choices_dict = dict(ContactMessage.SUBJECT_CHOICES)
        # Verify all expected choices exist
        expected_subjects = ['support', 'billing', 'feature', 'partnership', 'other']
        for subject in expected_subjects:
            self.assertIn(subject, choices_dict)

    def test_status_choices_translations(self):
        """Test that status choices support translation."""
        db_alias = get_db_alias()
        _contact = ContactMessageRepository.create(db_alias=db_alias, **self.contact_data)
        # The choices should use gettext_lazy for translation
        choices_dict = dict(ContactMessage.STATUS_CHOICES)
        # Verify all expected statuses exist
        expected_statuses = ['new', 'in_progress', 'resolved', 'closed']
        for status in expected_statuses:
            self.assertIn(status, choices_dict)


class ContactMessageQuerySetTest(TestCase):
    """Test cases for ContactMessage querysets and filtering."""

    def setUp(self):
        """Set up test data."""
        db_alias = get_db_alias()
        from uuid import uuid4
        suffix = uuid4().hex[:8]
        self.user1 = UserRepository.create_user(
            username=f'user1_{suffix}',
            email=f'user1_{suffix}@example.com',
            password='password123',
            db_alias=db_alias,
        )
        self.user2 = UserRepository.create_user(
            username=f'user2_{suffix}',
            email=f'user2_{suffix}@example.com',
            password='password123',
            db_alias=db_alias,
        )
        # Create contact messages with different attributes
        self.contact1 = ContactMessageRepository.create(
            db_alias=db_alias,
            name='Alice Smith',
            email='alice@example.com',
            subject='support',
            message='Technical support message with sufficient length.',
            status='new',
            user=self.user1
        )
        self.contact2 = ContactMessageRepository.create(
            db_alias=db_alias,
            name='Bob Johnson',
            email='bob@example.com',
            subject='billing',
            message='Billing inquiry message with sufficient length.',
            status='in_progress',
            user=self.user2
        )
        self.contact3 = ContactMessageRepository.create(
            db_alias=db_alias,
            name='Charlie Brown',
            email='charlie@example.com',
            subject='feature',
            message='Feature request message with sufficient length.',
            status='resolved'
            # No user associated
        )

    def test_filter_by_status(self):
        """Test filtering contact messages by status."""
        db_alias = get_db_alias()
        new_contacts = ContactMessageRepository.filter(db_alias=db_alias, status='new')
        self.assertEqual(new_contacts.count(), 1)
        self.assertEqual(new_contacts.first(), self.contact1)
        in_progress_contacts = ContactMessageRepository.filter(db_alias=db_alias, status='in_progress')
        self.assertEqual(in_progress_contacts.count(), 1)
        self.assertEqual(in_progress_contacts.first(), self.contact2)
        resolved_contacts = ContactMessageRepository.filter(db_alias=db_alias, status='resolved')
        self.assertEqual(resolved_contacts.count(), 1)
        self.assertEqual(resolved_contacts.first(), self.contact3)

    def test_filter_by_subject(self):
        """Test filtering contact messages by subject."""
        db_alias = get_db_alias()
        support_contacts = ContactMessageRepository.filter(db_alias=db_alias, subject='support')
        self.assertEqual(support_contacts.count(), 1)
        self.assertEqual(support_contacts.first(), self.contact1)
        billing_contacts = ContactMessageRepository.filter(db_alias=db_alias, subject='billing')
        self.assertEqual(billing_contacts.count(), 1)
        self.assertEqual(billing_contacts.first(), self.contact2)
        feature_contacts = ContactMessageRepository.filter(db_alias=db_alias, subject='feature')
        self.assertEqual(feature_contacts.count(), 1)
        self.assertEqual(feature_contacts.first(), self.contact3)

    def test_filter_by_user(self):
        """Test filtering contact messages by associated user."""
        db_alias = get_db_alias()
        user1_contacts = ContactMessageRepository.filter(db_alias=db_alias, user=self.user1)
        self.assertEqual(user1_contacts.count(), 1)
        self.assertEqual(user1_contacts.first(), self.contact1)
        user2_contacts = ContactMessageRepository.filter(db_alias=db_alias, user=self.user2)
        self.assertEqual(user2_contacts.count(), 1)
        self.assertEqual(user2_contacts.first(), self.contact2)
        # Test filtering for contacts without user
        no_user_contacts = ContactMessageRepository.filter(db_alias=db_alias, user__isnull=True)
        self.assertEqual(no_user_contacts.count(), 1)
        self.assertEqual(no_user_contacts.first(), self.contact3)

    def test_filter_by_email(self):
        """Test filtering contact messages by email."""
        db_alias = get_db_alias()
        alice_contacts = ContactMessageRepository.filter(db_alias=db_alias, email='alice@example.com')
        self.assertEqual(alice_contacts.count(), 1)
        self.assertEqual(alice_contacts.first(), self.contact1)
        # Test case-insensitive email filtering
        alice_contacts_upper = ContactMessageRepository.filter(db_alias=db_alias, email__iexact='ALICE@EXAMPLE.COM')
        self.assertEqual(alice_contacts_upper.count(), 1)

    def test_search_by_name(self):
        """Test searching contact messages by name."""
        db_alias = get_db_alias()
        alice_contacts = ContactMessageRepository.filter(db_alias=db_alias, name__icontains='Alice')
        self.assertEqual(alice_contacts.count(), 1)
        self.assertEqual(alice_contacts.first(), self.contact1)
        # Test partial name search
        smith_contacts = ContactMessageRepository.filter(db_alias=db_alias, name__icontains='Smith')
        self.assertEqual(smith_contacts.count(), 1)
        self.assertEqual(smith_contacts.first(), self.contact1)

    def test_search_by_message_content(self):
        """Test searching contact messages by message content."""
        db_alias = get_db_alias()
        support_messages = ContactMessageRepository.filter(db_alias=db_alias, message__icontains='Technical support')
        self.assertEqual(support_messages.count(), 1)
        self.assertEqual(support_messages.first(), self.contact1)
        billing_messages = ContactMessageRepository.filter(db_alias=db_alias, message__icontains='Billing inquiry')
        self.assertEqual(billing_messages.count(), 1)
        self.assertEqual(billing_messages.first(), self.contact2)

    def test_date_range_filtering(self):
        """Test filtering contact messages by date range."""
        # Clear any existing contacts to ensure clean state
        db_alias = get_db_alias()
        ContactMessageRepository.all(db_alias=db_alias).delete()
        # Create test contacts within this test method
        _contact1 = ContactMessageRepository.create(
            name='Alice Smith',
            email='alice@example.com',
            subject='support',
            message='Technical support message with sufficient length.',
            status='new',
            user=self.user1,
            db_alias=db_alias,
        )
        _contact2 = ContactMessageRepository.create(
            name='Bob Johnson',
            email='bob@example.com',
            subject='billing',
            message='Billing inquiry message with sufficient length.',
            status='in_progress',
            user=self.user2,
            db_alias=db_alias,
        )
        _contact3 = ContactMessageRepository.create(
            name='Charlie Brown',
            email='charlie@example.com',
            subject='feature',
            message='Feature request message with sufficient length.',
            status='resolved',
            db_alias=db_alias,
            # No user associated
        )
        # Verify contacts were created
        self.assertEqual(ContactMessageRepository.count(db_alias=db_alias), 3)
        # Use timezone-aware date filtering
        # Filter by the actual date when the contacts were created
        # Since all contacts are created in the same test, they should all have the same date
        actual_date = ContactMessageRepository.filter(db_alias=db_alias).values_list('created_at__date', flat=True)[0]
        # All contacts should be created on the same date as our test contacts
        today_contacts = ContactMessageRepository.filter(db_alias=db_alias, created_at__date=actual_date)
        self.assertEqual(today_contacts.count(), 3)
        # Test filtering by created_at range using datetime range instead of date
        start_of_day = django_timezone.make_aware(
            django_timezone.datetime.combine(actual_date,
                                             django_timezone.datetime.min.time())
        )
        end_of_day = django_timezone.make_aware(
            django_timezone.datetime.combine(actual_date,
                                             django_timezone.datetime.max.time())
        )
        day_contacts = ContactMessageRepository.filter(
            db_alias=db_alias,
            created_at__gte=start_of_day,
            created_at__lte=end_of_day
        )
        self.assertEqual(day_contacts.count(), 3)
        # Test filtering by created_at range (yesterday to today)
        yesterday = actual_date - django_timezone.timedelta(days=1)
        recent_contacts = ContactMessageRepository.filter(db_alias=db_alias, created_at__date__gte=yesterday)
        self.assertEqual(recent_contacts.count(), 3)

    def test_complex_filtering(self):
        """Test complex filtering combinations."""
        # Find new or in_progress support contacts
        db_alias = get_db_alias()
        active_support = ContactMessageRepository.filter(
            db_alias=db_alias,
            subject='support',
            status__in=['new', 'in_progress']
        )
        self.assertEqual(active_support.count(), 1)
        self.assertEqual(active_support.first(), self.contact1)
        # Find contacts with associated users that are not resolved
        user_contacts_active = ContactMessageRepository.filter(
            db_alias=db_alias,
            user__isnull=False
        ).exclude(status='resolved')
        self.assertEqual(user_contacts_active.count(), 2)

    def test_ordering_verification(self):
        """Test that default ordering works correctly."""
        db_alias = get_db_alias()
        all_contacts = list(ContactMessageRepository.all(db_alias=db_alias))
        # Should be ordered by created_at descending (newest first)
        for i in range(len(all_contacts) - 1):
            self.assertGreaterEqual(
                all_contacts[i].created_at,
                all_contacts[i + 1].created_at
            )


class ContactMessagePerformanceTest(TestCase):
    """Test cases for ContactMessage performance considerations."""

    def setUp(self):
        """Set up test data."""
        # Create multiple users and contact messages for performance testing
        db_alias = get_db_alias()
        from uuid import uuid4
        suffix = uuid4().hex[:8]
        self.users = []
        for i in range(10):
            user = UserRepository.create_user(
                username=f'user{i}_{suffix}',
                email=f'user{i}_{suffix}@example.com',
                password='password123',
                db_alias=db_alias,
            )
            self.users.append(user)

    def test_bulk_create_contact_messages(self):
        """Test bulk creation of contact messages."""
        db_alias = get_db_alias()
        contacts_data = []
        for i in range(100):
            contacts_data.append(
                ContactMessage(
                    name=f'Contact {i}',
                    email=f'contact{i}@example.com',
                    subject='support',
                    message=f'This is test message number {i} with sufficient length.',
                    user=self.users[i % 10] if i % 2 == 0 else None,
                )
            )
        # Bulk create should be efficient
        created_contacts = ContactMessageRepository.bulk_create(contacts_data, db_alias=db_alias)
        self.assertEqual(len(created_contacts), 100)
        # Verify they were actually created
        total_contacts = ContactMessageRepository.count(db_alias=db_alias)
        self.assertEqual(total_contacts, 100)

    def test_indexed_field_queries(self):
        """Test that queries on indexed fields are efficient."""
        # Create some test data
        db_alias = get_db_alias()
        ContactMessageRepository.bulk_create([
            ContactMessage(
                name=f'Contact {i}',
                email=f'contact{i}@example.com',
                subject='support' if i % 2 == 0 else 'billing',
                message=f'Test message {i} with sufficient length.',
                status='new' if i % 3 == 0 else 'in_progress'
            )
            for i in range(50)
        ], db_alias=db_alias)
        # Test queries on indexed fields (should be efficient)
        with self.assertNumQueries(1):
            list(ContactMessageRepository.filter(db_alias=db_alias, status='new'))
        with self.assertNumQueries(1):
            list(ContactMessageRepository.filter(db_alias=db_alias, subject='support'))
        with self.assertNumQueries(1):
            list(ContactMessageRepository.filter(db_alias=db_alias, email='contact1@example.com'))

    def test_select_related_user(self):
        """Test efficient querying with user relationship."""
        # Create contact messages with users
        db_alias = get_db_alias()
        for i in range(20):
            ContactMessageRepository.create(
                db_alias=db_alias,
                name=f'Contact {i}',
                email=f'contact{i}@example.com',
                subject='support',
                message=f'Test message {i} with sufficient length.',
                user=self.users[i % 10],
            )
        # Query without select_related (should make multiple queries)
        with self.assertNumQueries(21):  # 1 for contacts + 20 for users
            contacts = ContactMessageRepository.all(db_alias=db_alias)
            for contact in contacts:
                __ = contact.user.username if contact.user else None
        # Query with select_related (should make only 1 query)
        with self.assertNumQueries(1):
            contacts = ContactMessageRepository.select_related('user', db_alias=db_alias)
            for contact in contacts:
                __ = contact.user.username if contact.user else None


class ContactMessageAdminTest(TestCase):
    """Test cases for ContactMessage admin interface."""

    def setUp(self):
        """Set up test data."""
        db_alias = get_db_alias()
        from uuid import uuid4
        suffix = uuid4().hex[:8]
        self.site = AdminSite()
        self.admin = ContactMessageAdmin(ContactMessage, self.site)
        # Create test users
        self.superuser = UserRepository.create_superuser(
            db_alias=db_alias,
            username=f'admin_{suffix}',
            email=f'admin_{suffix}@example.com',
            password='adminpassword123'
        )
        self.staff_user = UserRepository.create_user(
            username=f'staff_{suffix}',
            email=f'staff_{suffix}@example.com',
            password='staffpassword123',
            is_staff=True,
            db_alias=db_alias,
        )
        self.regular_user = UserRepository.create_user(
            username=f'user_{suffix}',
            email=f'user_{suffix}@example.com',
            password='userpassword123',
            current_language='en',
            db_alias=db_alias,
        )
        # Create test contact messages
        self.contact1 = ContactMessageRepository.create(
            name='John Doe',
            email='john@example.com',
            subject='support',
            message='Technical support message with sufficient length.',
            status='new',
            user=self.regular_user,
            db_alias=db_alias,
        )
        self.contact2 = ContactMessageRepository.create(
            name='Jane Smith',
            email='jane@example.com',
            subject='billing',
            message='Billing inquiry message with sufficient length.',
            status='in_progress',
            db_alias=db_alias,
        )
        self.contact3 = ContactMessageRepository.create(
            name='Bob Johnson',
            email='bob@example.com',
            subject='feature',
            message='Feature request message with sufficient length.',
            status='resolved',
            db_alias=db_alias,
        )
        activate(self.regular_user.current_language)

    def test_admin_list_display(self):
        """Test that list display fields are correctly configured."""
        expected_fields = [
            'name',
            'email', 
            'subject',
            'status',
            'created_at',
            'updated_at'
        ]
        self.assertEqual(self.admin.list_display, expected_fields)

    def test_admin_list_filter(self):
        """Test that list filter fields are correctly configured."""
        expected_filters = [
            'status',
            'subject',
            'created_at',
            'updated_at'
        ]
        self.assertEqual(self.admin.list_filter, expected_filters)

    def test_admin_search_fields(self):
        """Test that search fields are correctly configured."""
        expected_search_fields = [
            'name',
            'email',
            'message',
            'admin_notes'
        ]
        self.assertEqual(self.admin.search_fields, expected_search_fields)

    def test_admin_readonly_fields(self):
        """Test that readonly fields are correctly configured."""
        expected_readonly_fields = [
            'created_at',
            'updated_at',
            'user'
        ]
        self.assertEqual(self.admin.readonly_fields, expected_readonly_fields)

    def test_admin_fields_configuration(self):
        """Test that field ordering is correctly configured."""
        expected_fields = [
            'name', 'email', 'subject', 'message', 'status', 'admin_notes',
            'user', 'created_at', 'updated_at'
        ]
        self.assertEqual(self.admin.fields, expected_fields)

    def test_admin_ordering(self):
        """Test that default ordering is correctly configured."""
        expected_ordering = ['-created_at']
        self.assertEqual(self.admin.ordering, expected_ordering)

    def test_admin_list_per_page(self):
        """Test that pagination is correctly configured."""
        self.assertEqual(self.admin.list_per_page, 25)

    def test_admin_get_queryset_optimization(self):
        """Test that queryset is optimized with select_related."""
        db_alias = get_db_alias()
        request = HttpRequest()
        request.user = self.staff_user
        queryset = self.admin.get_queryset(request, db_alias=db_alias)
        # Check that the queryset includes select_related for user
        # This is a bit tricky to test directly, but we can check the query
        self.assertIn('user', str(queryset.query))

    def test_admin_delete_permissions_superuser(self):
        """Test that superuser can delete contact messages."""
        request = HttpRequest()
        request.user = self.superuser
        # Superuser should have delete permission
        self.assertTrue(self.admin.has_delete_permission(request))
        self.assertTrue(self.admin.has_delete_permission(request, self.contact1))

    def test_admin_delete_permissions_staff(self):
        """Test that staff user cannot delete contact messages."""
        request = HttpRequest()
        request.user = self.staff_user
        # Staff user should not have delete permission
        self.assertFalse(self.admin.has_delete_permission(request))
        self.assertFalse(self.admin.has_delete_permission(request, self.contact1))

    def test_admin_actions_available(self):
        """Test that custom actions are available."""
        expected_actions = ['mark_as_in_progress', 'mark_as_resolved', 'mark_as_closed']
        for action in expected_actions:
            self.assertIn(action, self.admin.actions)

    def test_admin_action_mark_as_in_progress(self):
        """Test mark_as_in_progress action."""
        db_alias = get_db_alias()
        request = HttpRequest()
        request.user = self.staff_user
        request.session = {}
        request._messages = FallbackStorage(request)
        # Create queryset with contacts to update
        queryset = ContactMessageRepository.filter(
            id__in=[self.contact1.id, self.contact3.id], db_alias=db_alias)
        # Execute the action
        self.admin.mark_as_in_progress(request, queryset)
        # Check that contacts were updated
        self.contact1.refresh_from_db(using=db_alias)
        self.contact3.refresh_from_db(using=db_alias)
        self.assertEqual(self.contact1.status, 'in_progress')
        self.assertEqual(self.contact3.status, 'in_progress')

    def test_admin_action_mark_as_resolved(self):
        """Test mark_as_resolved action."""
        db_alias = get_db_alias()
        request = HttpRequest()
        request.user = self.staff_user
        request.session = {}
        request._messages = FallbackStorage(request)
        # Create queryset with contacts to update
        queryset = ContactMessageRepository.filter(
            id__in=[self.contact1.id, self.contact2.id], db_alias=db_alias)
        # Execute the action
        self.admin.mark_as_resolved(request, queryset)
        # Check that contacts were updated
        self.contact1.refresh_from_db(using=db_alias)
        self.contact2.refresh_from_db(using=db_alias)
        self.assertEqual(self.contact1.status, 'resolved')
        self.assertEqual(self.contact2.status, 'resolved')

    def test_admin_action_mark_as_closed(self):
        """Test mark_as_closed action."""
        db_alias = get_db_alias()
        request = HttpRequest()
        request.user = self.staff_user
        request.session = {}
        request._messages = FallbackStorage(request)
        # Create queryset with contacts to update
        queryset = ContactMessageRepository.filter(id=self.contact1.id, db_alias=db_alias)
        # Execute the action
        self.admin.mark_as_closed(request, queryset)
        # Check that contact was updated
        self.contact1.refresh_from_db(using=db_alias)
        self.assertEqual(self.contact1.status, 'closed')

    def test_admin_action_descriptions(self):
        """Test that action descriptions are properly set."""
        self.assertEqual(
            self.admin.mark_as_in_progress.short_description,
            'Mark as in progress'
        )
        self.assertEqual(
            self.admin.mark_as_resolved.short_description,
            'Mark as resolved'
        )
        self.assertEqual(
            self.admin.mark_as_closed.short_description,
            'Mark as closed'
        )

    def test_admin_integration_with_model(self):
        """Test admin integration with ContactMessage model."""
        # Check that ContactMessage is registered in admin
        self.assertIn(ContactMessage, admin.site._registry)
        # Check that the correct admin class is registered
        self.assertIsInstance(
            admin.site._registry[ContactMessage],
            ContactMessageAdmin
        )

    def test_admin_bulk_actions_performance(self):
        """Test that bulk actions work efficiently with multiple records."""
        # Create multiple contact messages
        db_alias = get_db_alias()
        contacts = []
        for i in range(10):
            contact = ContactMessageRepository.create(
                name=f'Bulk Contact {i}',
                email=f'bulk{i}@example.com',
                subject='support',
                message=f'Bulk test message {i} with sufficient length.',
                status='new',
                db_alias=db_alias,
            )
            contacts.append(contact)
        request = HttpRequest()
        request.user = self.staff_user
        request.session = {}
        request._messages = FallbackStorage(request)
        # Test bulk update
        queryset = ContactMessageRepository.filter(
            id__in=[contact.id for contact in contacts],
            db_alias=db_alias
        )
        self.admin.mark_as_resolved(request, queryset)
        # Verify all contacts were updated
        for contact in contacts:
            contact.refresh_from_db(using=db_alias)
            self.assertEqual(contact.status, 'resolved')

    def test_admin_queryset_with_user_relationship(self):
        """Test that admin queryset properly handles user relationships."""
        db_alias = get_db_alias()
        request = HttpRequest()
        request.user = self.staff_user
        queryset = self.admin.get_queryset(request, db_alias=db_alias)
        # Should include all contact messages
        self.assertEqual(queryset.count(), 3)
        # Should be ordered by created_at descending
        ordered_contacts = list(queryset)
        self.assertTrue(ordered_contacts[0].created_at >= ordered_contacts[1].created_at >= ordered_contacts[2].created_at) # pylint: disable=line-too-long
