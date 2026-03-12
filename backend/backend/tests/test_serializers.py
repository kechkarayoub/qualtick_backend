# pylint: disable=protected-access,too-many-instance-attributes
"""
Comprehensive test suite for backend serializers.

This module provides tests for:
- ContactMessageSerializer functionality
- ContactMessageListSerializer functionality
- ContactMessageSerializer integration with API views

Tests extracted from test_models.py and test_models2.py for better organization.
"""

from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.utils.translation import activate
from rest_framework.test import APIClient, APIRequestFactory

from accounts.repositories import UserRepository
from backend.models import ContactMessage
from backend.repositories import ContactMessageRepository
from backend.serializers import ContactMessageSerializer, ContactMessageListSerializer
from backend.utils import get_db_alias

User = get_user_model()


class ContactMessageSerializerTest(TestCase):
    """Test cases for ContactMessage serializers."""

    def setUp(self):
        """Set up test data."""
        db_alias = get_db_alias()
        suffix = uuid4().hex[:8]
        self.factory = APIRequestFactory()
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
            'message': 'This is a test message with sufficient length to pass validation.'
        }
        self.contact_message = ContactMessageRepository.create(
            **self.valid_contact_data,
            user=self.user,
            status='new',
            db_alias=db_alias
        )
        activate(self.user.current_language)

    def test_contact_message_serializer_valid_data(self):
        """Test ContactMessageSerializer with valid data."""
        serializer = ContactMessageSerializer(data=self.valid_contact_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['name'], 'John Doe')
        self.assertEqual(serializer.validated_data['email'], 'john.doe@example.com')
        self.assertEqual(serializer.validated_data['subject'], 'support')
        self.assertEqual(serializer.validated_data['message'],
                'This is a test message with sufficient length to pass validation.')

    def test_contact_message_serializer_create_without_user(self):
        """Test creating contact message without authenticated user."""
        db_alias = get_db_alias()
        # Create serializer without request context
        serializer = ContactMessageSerializer(data=self.valid_contact_data)
        self.assertTrue(serializer.is_valid())
        contact = serializer.save()
        self.assertEqual(contact.name, 'John Doe')
        self.assertEqual(contact.email, 'john.doe@example.com')
        self.assertEqual(contact.subject, 'support')
        self.assertIsNone(contact.user)  # No user should be associated

    def test_contact_message_serializer_create_with_authenticated_user(self):
        """Test creating contact message with authenticated user."""
        db_alias = get_db_alias()
        # Create a mock request with authenticated user
        request = self.factory.post('/')
        request.user = self.user
        # Create serializer with request context
        serializer = ContactMessageSerializer(
            data=self.valid_contact_data,
            context={'request': request}
        )
        self.assertTrue(serializer.is_valid())
        contact = serializer.save()
        self.assertEqual(contact.name, 'John Doe')
        self.assertEqual(contact.email, 'john.doe@example.com')
        self.assertEqual(contact.subject, 'support')
        self.assertEqual(contact.user, self.user)  # User should be associated

    def test_contact_message_serializer_create_with_anonymous_user(self):
        """Test creating contact message with anonymous user."""
        db_alias = get_db_alias()
        # Create a mock request with anonymous user
        request = self.factory.post('/')
        request.user = AnonymousUser()
        # Create serializer with request context
        serializer = ContactMessageSerializer(
            data=self.valid_contact_data,
            context={'request': request}
        )
        self.assertTrue(serializer.is_valid())
        contact = serializer.save()
        self.assertEqual(contact.name, 'John Doe')
        self.assertIsNone(contact.user)  # No user should be associated

    def test_contact_message_serializer_invalid_message_too_short(self):
        """Test ContactMessageSerializer with message too short."""
        db_alias = get_db_alias()
        data = self.valid_contact_data.copy()
        data['message'] = 'Too short'  # Only 9 characters
        serializer = ContactMessageSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('message', serializer.errors)
        self.assertIn('at least 10 characters', str(serializer.errors['message'][0]))

    def test_contact_message_serializer_message_with_whitespace(self):
        """Test ContactMessageSerializer strips whitespace from message.""" 
        db_alias = get_db_alias()
        data = self.valid_contact_data.copy()
        data['message'] = '   This is a test message with sufficient length.   '
        serializer = ContactMessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(
            serializer.validated_data['message'],
            'This is a test message with sufficient length.'
        )

    def test_contact_message_serializer_invalid_name_empty(self):
        """Test ContactMessageSerializer with empty name."""     
        db_alias = get_db_alias()   
        # Test completely empty name (triggers Django's built-in validation)
        data = self.valid_contact_data.copy()
        data['name'] = ''  # Empty string
        serializer = ContactMessageSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
        # Django's built-in validation for blank fields
        self.assertIn('This field may not be blank', str(serializer.errors['name'][0]))
        # Test whitespace-only name (should trigger our custom validator if it gets that far)
        # But actually, this will also be caught by Django's validation
        data['name'] = '   '  # Only whitespace
        serializer = ContactMessageSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
        # This could be either Django's validation or our custom one
        error_message = str(serializer.errors['name'][0])
        self.assertTrue(
            'This field may not be blank' in error_message or 'Name is required' in error_message
        )

    def test_contact_message_serializer_custom_name_validation(self):
        """Test ContactMessageSerializer custom name validation that actually
        triggers our validator."""
        db_alias = get_db_alias()
        # Test a name that passes Django's basic validation but fails our custom validation
        # This is tricky because CharField with blank=False will catch most cases
        # Our custom validator mainly serves to strip whitespace and provide custom message
        # Test that our validator strips whitespace properly
        data = self.valid_contact_data.copy()
        data['name'] = '  Valid Name  '  # Name with whitespace
        serializer = ContactMessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
         # Should be stripped
        self.assertEqual(serializer.validated_data['name'], 'Valid Name')

    def test_contact_message_serializer_name_with_whitespace(self):
        """Test ContactMessageSerializer strips whitespace from name."""
        db_alias = get_db_alias()      
        data = self.valid_contact_data.copy()
        data['name'] = '   John Doe   '
        serializer = ContactMessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['name'], 'John Doe')

    def test_contact_message_serializer_missing_required_fields(self):
        """Test ContactMessageSerializer with missing required fields."""
        db_alias = get_db_alias()
        # Test missing name
        data = self.valid_contact_data.copy()
        del data['name']
        serializer = ContactMessageSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
        # Test missing email
        data = self.valid_contact_data.copy()
        del data['email']
        serializer = ContactMessageSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)
        # Test missing subject
        data = self.valid_contact_data.copy()
        del data['subject']
        serializer = ContactMessageSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('subject', serializer.errors)
        # Test missing message
        data = self.valid_contact_data.copy()
        del data['message']
        serializer = ContactMessageSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('message', serializer.errors)

    def test_contact_message_serializer_invalid_email(self):
        """Test ContactMessageSerializer with invalid email format."""
        db_alias = get_db_alias()
        data = self.valid_contact_data.copy()
        data['email'] = 'invalid-email-format'
        serializer = ContactMessageSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_contact_message_serializer_invalid_subject_choice(self):
        """Test ContactMessageSerializer with invalid subject choice."""
        db_alias = get_db_alias()
        data = self.valid_contact_data.copy()
        data['subject'] = 'invalid_subject'
        serializer = ContactMessageSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('subject', serializer.errors)

    def test_contact_message_serializer_serialization(self):
        """Test ContactMessageSerializer serialization of existing object."""        
        serializer = ContactMessageSerializer(self.contact_message)
        data = serializer.data
        self.assertEqual(data['id'], self.contact_message.id)
        self.assertEqual(data['name'], 'John Doe')
        self.assertEqual(data['email'], 'john.doe@example.com')
        self.assertEqual(data['subject'], 'support')
        self.assertEqual(data['message'],
                'This is a test message with sufficient length to pass validation.')
        self.assertIn('created_at', data)

    def test_contact_message_serializer_read_only_fields(self):
        """Test that read-only fields cannot be updated."""
        db_alias = get_db_alias()
        data = self.valid_contact_data.copy()
        data['id'] = 999  # Try to set read-only field
        data['created_at'] = '2020-01-01T00:00:00Z'  # Try to set read-only field
        serializer = ContactMessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        contact = serializer.save()
        # ID should be auto-generated, not 999
        self.assertNotEqual(contact.id, 999)
        # created_at should be auto-generated, not the provided value
        self.assertNotEqual(
            contact.created_at.strftime('%Y-%m-%d'),
            '2020-01-01'
        )


class ContactMessageListSerializerTest(TestCase):
    """Test cases for ContactMessageListSerializer."""
    def setUp(self):
        """Set up test data."""
        db_alias = get_db_alias()
        suffix = uuid4().hex[:8]
        self.user = UserRepository.create_user(
            username=f'testusermsgsr_{suffix}',
            email=f'testusermsgsr_{suffix}@example.com',
            password='testpassword123',
            current_language='en',
            db_alias=db_alias
        )
        self.contact_message = ContactMessageRepository.create(
            name='John Doe',
            email='john.doe@example.com',
            subject='support',
            message='This is a test message with sufficient length to pass validation.',
            status='in_progress',
            user=self.user,
            db_alias=db_alias
        )
        activate(self.user.current_language)

    def test_contact_message_list_serializer_serialization(self):
        """Test ContactMessageListSerializer serialization."""        
        serializer = ContactMessageListSerializer(self.contact_message)
        data = serializer.data
        self.assertEqual(data['id'], self.contact_message.id)
        self.assertEqual(data['name'], 'John Doe')
        self.assertEqual(data['email'], 'john.doe@example.com')
        self.assertEqual(data['subject'], 'support')
        self.assertEqual(data['subject_display'], 'Technical Support')
        self.assertEqual(data['status'], 'in_progress')
        self.assertEqual(data['status_display'], 'In Progress')
        self.assertIn('created_at', data)
        self.assertIn('updated_at', data)

    def test_contact_message_list_serializer_multiple_objects(self):
        """Test ContactMessageListSerializer with multiple objects."""  
        db_alias = get_db_alias()      
        # Create additional contact messages
        contact2 = ContactMessageRepository.create(
            name='Jane Smith',
            email='jane.smith@example.com',
            subject='billing',
            message='Billing inquiry message with sufficient length.',
            status='resolved',
            db_alias=db_alias
        )
        contact3 = ContactMessageRepository.create(
            name='Bob Johnson',
            email='bob.johnson@example.com',
            subject='feature',
            message='Feature request message with sufficient length.',
            status='new',
            db_alias=db_alias
        )
        contacts = [self.contact_message, contact2, contact3]
        serializer = ContactMessageListSerializer(contacts, many=True)
        data = serializer.data
        self.assertEqual(len(data), 3)
        # Check first contact
        self.assertEqual(data[0]['name'], 'John Doe')
        self.assertEqual(data[0]['subject_display'], 'Technical Support')
        self.assertEqual(data[0]['status_display'], 'In Progress')
        # Check second contact
        self.assertEqual(data[1]['name'], 'Jane Smith')
        self.assertEqual(data[1]['subject_display'], 'Billing & Account')
        self.assertEqual(data[1]['status_display'], 'Resolved')
        # Check third contact
        self.assertEqual(data[2]['name'], 'Bob Johnson')
        self.assertEqual(data[2]['subject_display'], 'Feature Request')
        self.assertEqual(data[2]['status_display'], 'New')

    def test_contact_message_list_serializer_all_subject_choices(self):
        """Test ContactMessageListSerializer with all subject choices."""
        db_alias = get_db_alias()
        subjects = [
            ('support', 'Technical Support'),
            ('billing', 'Billing & Account'),
            ('feature', 'Feature Request'),
            ('partnership', 'Partnership'),
            ('other', 'Other')
        ]
        contacts = []
        for subject, expected_display in subjects:
            contact = ContactMessageRepository.create(
                name=f'Test {subject}',
                email=f'{subject}@example.com',
                subject=subject,
                message=f'Test message for {subject} with sufficient length.',
                db_alias=db_alias
            )
            contacts.append(contact)
        serializer = ContactMessageListSerializer(contacts, many=True)
        data = serializer.data
        for i, (subject, expected_display) in enumerate(subjects):
            self.assertEqual(data[i]['subject'], subject)
            self.assertEqual(data[i]['subject_display'], expected_display)

    def test_contact_message_list_serializer_all_status_choices(self):
        """Test ContactMessageListSerializer with all status choices."""
        db_alias = get_db_alias()
        statuses = [
            ('new', 'New'),
            ('in_progress', 'In Progress'),
            ('resolved', 'Resolved'),
            ('closed', 'Closed')
        ]
        contacts = []
        for status, expected_display in statuses:
            contact = ContactMessageRepository.create(
                name=f'Test {status}',
                email=f'{status}@example.com',
                subject='support',
                message=f'Test message for {status} with sufficient length.',
                status=status,
                db_alias=db_alias
            )
            contacts.append(contact)
        serializer = ContactMessageListSerializer(contacts, many=True)
        data = serializer.data
        for i, (status, expected_display) in enumerate(statuses):
            self.assertEqual(data[i]['status'], status)
            self.assertEqual(data[i]['status_display'], expected_display)

    def test_contact_message_list_serializer_read_only_fields(self):
        """Test that all fields in list serializer are read-only as expected."""        
        serializer = ContactMessageListSerializer()
        meta = serializer.Meta
        expected_read_only = ['id', 'created_at', 'updated_at']
        for field in expected_read_only:
            self.assertIn(field, meta.read_only_fields)


class ContactMessageSerializerIntegrationTest(TestCase):
    """Integration tests for ContactMessage serializers with API views."""

    def setUp(self):
        """Set up test data."""   
        db_alias = get_db_alias()
        suffix = uuid4().hex[:8]
        self.client = APIClient()
        self.user = UserRepository.create_user(
            username=f'testusermsgsrint_{suffix}',
            email=f'testusermsgsrint_{suffix}@example.com',
            password='testpassword123',
            current_language='en',
            db_alias=db_alias
        )

    def test_serializer_with_api_client_authenticated(self):
        """Test serializer integration with authenticated API client."""
        db_alias = get_db_alias()
        # This test would require actual API endpoints to be meaningful
        # For now, we'll test the serializer context handling
        factory = APIRequestFactory()
        request = factory.post('/')
        request.user = self.user
        data = {
            'name': 'API Test User',
            'email': 'apitest@example.com',
            'subject': 'support',
            'message': 'This is an API test message with sufficient length.'
        }
        serializer = ContactMessageSerializer(
            data=data,
            context={'request': request}
        )
        self.assertTrue(serializer.is_valid())
        contact = serializer.save()
        # Verify the user was automatically associated
        self.assertEqual(contact.user, self.user)
        self.assertEqual(contact.name, 'API Test User')

    def test_serializer_validation_edge_cases(self):
        """Test serializer validation with edge cases."""   
        db_alias = get_db_alias()     
        # Test message with exactly 10 characters (minimum)
        data = {
            'name': 'Edge Case',
            'email': 'edge@example.com',
            'subject': 'support',
            'message': '1234567890'  # Exactly 10 characters
        }
        serializer = ContactMessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        # Test message with 9 characters (should fail)
        data['message'] = '123456789'  # 9 characters
        serializer = ContactMessageSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        # Test name with only whitespace variations
        test_names = ['', '   ', '\t\t', '\n\n', '  \t \n  ']
        for name in test_names:
            data = {
                'name': name,
                'email': 'test@example.com',
                'subject': 'support',
                'message': 'Valid message with sufficient length.'
            }
            serializer = ContactMessageSerializer(data=data)
            self.assertFalse(serializer.is_valid())
            self.assertIn('name', serializer.errors)
