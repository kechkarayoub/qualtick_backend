"""Models for handling contact form messages."""
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class ContactMessage(models.Model):
    """
    Model to store contact form messages from users
    """
    SUBJECT_CHOICES = [
        ('support', _('Technical Support')),
        ('billing', _('Billing & Account')),
        ('feature', _('Feature Request')),
        ('partnership', _('Partnership')),
        ('other', _('Other')),
    ]
    STATUS_CHOICES = [
        ('new', _('New')),
        ('in_progress', _('In Progress')),
        ('resolved', _('Resolved')),
        ('closed', _('Closed')),
    ]
    # Basic contact information
    name = models.CharField(
        max_length=100,
        verbose_name=_('Full Name'),
        help_text=_('The full name of the person contacting us')
    )
    email = models.EmailField(
        verbose_name=_('Email Address'),
        help_text=_('Email address for response')
    )
    subject = models.CharField(
        max_length=20,
        choices=SUBJECT_CHOICES,
        verbose_name=_('Subject'),
        help_text=_('Category of the inquiry')
    )
    message = models.TextField(
        validators=[MinLengthValidator(10)],
        verbose_name=_('Message'),
        help_text=_('The detailed message from the user')
    )
    # Status and tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        verbose_name=_('Status'),
        help_text=_('Current status of the message')
    )
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
        help_text=_('When the message was submitted')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At'),
        help_text=_('When the message was last updated')
    )
    # Optional: Link to user if they're authenticated
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('User'),
        help_text=_('Associated user account if logged in')
    )
    # Admin notes
    admin_notes = models.TextField(
        blank=True,
        verbose_name=_('Admin Notes'),
        help_text=_('Internal notes for administrators')
    )

    class Meta:
        db_table = 'backend_contact_message'
        ordering = ['-created_at']
        verbose_name = _('Contact Message')
        verbose_name_plural = _('Contact Messages')
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['subject']),
            models.Index(fields=['created_at']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_subject_display()} ({self.created_at.strftime('%Y-%m-%d')})" # pylint: disable=line-too-long

    def get_subject_display_translated(self):
        """Get the translated subject display"""
        return dict(self.SUBJECT_CHOICES)[self.subject]

    def get_status_display_translated(self):
        """Get the translated status display"""
        return dict(self.STATUS_CHOICES)[self.status]
