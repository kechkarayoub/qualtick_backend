"""
Tests for ContactMessageRepository.
"""
from uuid import uuid4

from django.test import TestCase
from django.contrib.auth import get_user_model

from accounts.repositories import UserRepository
from backend.repositories import ContactMessageRepository
from backend.utils import get_db_alias


User = get_user_model()


class ContactMessageRepositoryTest(TestCase):
    """Tests for ContactMessageRepository."""
    
    def setUp(self):
        """Set up test data."""
        db_alias = get_db_alias()
        suffix = uuid4().hex[:8]
        self.user = UserRepository.create_user(
            username=f'testuser_{suffix}',
            email=f'test_{suffix}@example.com',
            password='testpass123',
            db_alias=db_alias
        )
        
        # Create test messages
        self.message1 = ContactMessageRepository.create(
            name='John Doe',
            email='john@example.com',
            subject='support',
            message='Need help with something',
            status='new',
            db_alias=db_alias
        )
        
        self.message2 = ContactMessageRepository.create(
            name='Jane Smith',
            email='jane@example.com',
            subject='billing',
            message='Question about billing',
            status='in_progress',
            user_id=self.user.id,
            db_alias=db_alias
        )
    
    def test_get_by_id(self):
        """Test retrieving message by ID."""
        db_alias = get_db_alias()
        message = ContactMessageRepository.get_by_id(self.message1.id, db_alias=db_alias)
        self.assertIsNotNone(message)
        self.assertEqual(message.email, 'john@example.com')
    
    def test_get_by_email(self):
        """Test retrieving messages by email."""
        db_alias = get_db_alias()
        messages = ContactMessageRepository.get_by_email('john@example.com', db_alias=db_alias)
        self.assertEqual(messages.count(), 1)
        self.assertEqual(messages.first().name, 'John Doe')
    
    def test_get_by_user(self):
        """Test retrieving messages by user."""
        db_alias = get_db_alias()
        messages = ContactMessageRepository.get_by_user(self.user.id, db_alias=db_alias)
        self.assertEqual(messages.count(), 1)
        self.assertEqual(messages.first().email, 'jane@example.com')
    
    def test_get_by_status(self):
        """Test retrieving messages by status."""
        db_alias = get_db_alias()
        new_messages = ContactMessageRepository.get_by_status('new', db_alias=db_alias)
        self.assertEqual(new_messages.count(), 1)
        
        in_progress = ContactMessageRepository.get_by_status('in_progress', db_alias=db_alias)
        self.assertEqual(in_progress.count(), 1)
    
    def test_get_pending(self):
        """Test retrieving pending messages."""
        db_alias = get_db_alias()
        pending = ContactMessageRepository.get_pending(db_alias=db_alias)
        self.assertEqual(pending.count(), 2)  # Both 'new' and 'in_progress'
    
    def test_update_status(self):
        """Test updating message status."""
        db_alias = get_db_alias()
        updated = ContactMessageRepository.update_status(
            self.message1.id,
            'resolved',
            admin_notes='Issue resolved',
            db_alias=db_alias
        )
        
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, 'resolved')
        self.assertEqual(updated.admin_notes, 'Issue resolved')
    
    def test_search(self):
        """Test searching messages."""
        db_alias = get_db_alias()
        results = ContactMessageRepository.search('billing', db_alias=db_alias)
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().subject, 'billing')
    
    def test_get_statistics(self):
        """Test getting statistics."""
        db_alias = get_db_alias()
        stats = ContactMessageRepository.get_statistics(db_alias=db_alias)
        
        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['new'], 1)
        self.assertEqual(stats['in_progress'], 1)
        self.assertEqual(stats['resolved'], 0)
        self.assertEqual(stats['closed'], 0)
    
    def test_create(self):
        """Test creating a new message."""
        db_alias = get_db_alias()
        message = ContactMessageRepository.create(
            name='Test User',
            email='test@test.com',
            subject='feature',
            message='Feature request here',
            db_alias=db_alias
        )
        
        self.assertIsNotNone(message.id)
        self.assertEqual(message.status, 'new')  # Default status
    
    def test_delete(self):
        """Test deleting a message."""
        db_alias = get_db_alias()
        message_id = self.message1.id
        result = ContactMessageRepository.delete(message_id, db_alias=db_alias)
        
        self.assertTrue(result)
        self.assertIsNone(ContactMessageRepository.get_by_id(message_id, db_alias=db_alias))
    
    def test_exists(self):
        """Test checking if message exists."""
        db_alias = get_db_alias()
        exists = ContactMessageRepository.exists(email='john@example.com', db_alias=db_alias)
        self.assertTrue(exists)
        
        not_exists = ContactMessageRepository.exists(email='nonexistent@example.com', db_alias=db_alias)
        self.assertFalse(not_exists)
    
    def test_count(self):
        """Test counting messages."""
        db_alias = get_db_alias()
        total = ContactMessageRepository.count(db_alias=db_alias)
        self.assertEqual(total, 2)
        
        support_count = ContactMessageRepository.count(subject='support', db_alias=db_alias)
        self.assertEqual(support_count, 1)
