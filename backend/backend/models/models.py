"""Models for handling contact form messages and audit logs."""
import json
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


class AuditLog(models.Model):
    """
    Immutable audit trail for every significant user action.

    Design decisions:
    - user is SET_NULL so logs survive account deletion.
    - extra_data stores arbitrary JSON payload (request body snapshot, diff, …).
    - ip_address / user_agent captured for forensic / security analysis.
    - Records are never updated or deleted programmatically.
    """

    ACTION_CREATE = 'create'
    ACTION_READ   = 'read'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_LOGIN  = 'login'
    ACTION_LOGOUT = 'logout'
    ACTION_LOGIN_FAILED = 'login_failed'
    ACTION_PASSWORD_CHANGE = 'password_change'
    ACTION_PASSWORD_RESET  = 'password_reset'
    ACTION_EMAIL_CHANGE    = 'email_change'
    ACTION_EMAIL_VERIFY    = 'email_verify'
    ACTION_PHONE_VERIFY    = 'phone_verify'
    ACTION_PROFILE_UPDATE  = 'profile_update'
    ACTION_ACCOUNT_DELETE  = 'account_delete'
    ACTION_OTHER           = 'other'

    ACTION_CHOICES = [
        (ACTION_CREATE,          _('Create')),
        (ACTION_READ,            _('Read')),
        (ACTION_UPDATE,          _('Update')),
        (ACTION_DELETE,          _('Delete')),
        (ACTION_LOGIN,           _('Login')),
        (ACTION_LOGOUT,          _('Logout')),
        (ACTION_LOGIN_FAILED,    _('Login Failed')),
        (ACTION_PASSWORD_CHANGE, _('Password Change')),
        (ACTION_PASSWORD_RESET,  _('Password Reset')),
        (ACTION_EMAIL_CHANGE,    _('Email Change')),
        (ACTION_EMAIL_VERIFY,    _('Email Verify')),
        (ACTION_PHONE_VERIFY,    _('Phone Verify')),
        (ACTION_PROFILE_UPDATE,  _('Profile Update')),
        (ACTION_ACCOUNT_DELETE,  _('Account Delete')),
        (ACTION_OTHER,           _('Other')),
    ]

    OUTCOME_SUCCESS = 'success'
    OUTCOME_FAILURE = 'failure'
    OUTCOME_CHOICES = [
        (OUTCOME_SUCCESS, _('Success')),
        (OUTCOME_FAILURE, _('Failure')),
    ]

    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_('User'),
    )
    actor_username = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name=_('Actor Username'),
        help_text=_('Snapshot of username at the time of the action (survives user deletion)'),
    )
    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        db_index=True,
        verbose_name=_('Action'),
    )
    outcome = models.CharField(
        max_length=10,
        choices=OUTCOME_CHOICES,
        default=OUTCOME_SUCCESS,
        db_index=True,
        verbose_name=_('Outcome'),
    )
    resource_type = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_index=True,
        verbose_name=_('Resource Type'),
        help_text=_('Django model label, e.g. "accounts.User"'),
    )
    resource_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        db_index=True,
        verbose_name=_('Resource ID'),
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Description'),
        help_text=_('Human-readable summary of the action'),
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address'),
    )
    user_agent = models.TextField(
        blank=True,
        default='',
        verbose_name=_('User Agent'),
    )
    request_method = models.CharField(
        max_length=10,
        blank=True,
        default='',
        verbose_name=_('HTTP Method'),
    )
    request_path = models.CharField(
        max_length=500,
        blank=True,
        default='',
        verbose_name=_('Request Path'),
    )
    extra_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Extra Data'),
        help_text=_('Additional structured data (diff, payload snapshot, …)'),
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_('Timestamp'),
    )

    class Meta:
        db_table = 'backend_audit_log'
        ordering = ['-timestamp']
        verbose_name = _('Audit Log')
        verbose_name_plural = _('Audit Logs')
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['outcome', 'timestamp']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        actor = self.actor_username or (str(self.user_id) if self.user_id else 'anonymous')
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {actor} – {self.action} – {self.outcome}"

    def get_extra_data_display(self):
        if self.extra_data is None:
            return ''
        try:
            return json.dumps(self.extra_data, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(self.extra_data)
