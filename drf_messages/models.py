import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

DRF_MESSAGE_USER_MODEL = getattr(settings, 'DRF_MESSAGE_USER_MODEL')


class MessageManager(models.Manager):

    def inbox_for(self, recipient):
        """
        :param recipient: is the instance of the 'actual' message user model
        :returns: all messages received by the given user and are not
        marked as deleted.
        """
        return self.filter(
            recipient=recipient,
            recipient_deleted_at__isnull=True,
        )

    def outbox_for(self, sender):
        """
        :param sender: is the instance of the 'actual' message user model
        :returns: all messages sent by the given user and are not
        marked as deleted.
        """
        return self.filter(
            sender=sender,
            sender_deleted_at__isnull=True,
        )

    def trash_for(self, recipient_or_sender):
        """
        :param recipient_or_sender: is the instance of the 'actual' message user model
        :returns: all messages that were either received or sent by the given
        user and are marked as deleted.
        """
        return self.filter(
            recipient=recipient_or_sender,
            recipient_deleted_at__isnull=False,
        ) | self.filter(
            sender=recipient_or_sender,
            sender_deleted_at__isnull=False,
        )


class Message(models.Model):
    """
    A private message from user to user
    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    subject = models.CharField(max_length=140)
    body = models.TextField()
    sender = models.ForeignKey(DRF_MESSAGE_USER_MODEL, related_name='sent_messages', on_delete=models.SET_NULL, null=True)
    recipient = models.ForeignKey(DRF_MESSAGE_USER_MODEL, related_name='received_messages', null=True, blank=True, on_delete=models.SET_NULL)
    parent_msg = models.ForeignKey('self', related_name='next_messages', null=True, blank=True, on_delete=models.SET_NULL)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    sender_deleted_at = models.DateTimeField(null=True, blank=True)
    recipient_deleted_at = models.DateTimeField(null=True, blank=True)

    objects = MessageManager()

    def new(self):
        """returns whether the recipient has read the message or not"""
        if self.read_at is not None:
            return False
        return True

    def replied(self):
        """returns whether the recipient has written a reply to this message"""
        if self.replied_at is not None:
            return True
        return False

    def __str__(self):
        return self.subject

    def save(self, **kwargs):
        if not self.id:
            self.sent_at = timezone.now()
        super().save(**kwargs)

    class Meta:
        ordering = ['-sent_at']
        verbose_name = "Message"
        verbose_name_plural = "Messages"
