from django.conf import settings
from django.db import models, transaction
from django.db.models import signals, Q
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class MessageManager(models.Manager):

    def inbox_for(self, user):
        """
        Returns all messages that were received by the given user and are not
        marked as deleted.
        """
        return self.filter(
            recipient=user,
            recipient_deleted_at__isnull=True,
        )

    def outbox_for(self, user):
        """
        Returns all messages that were sent by the given user and are not
        marked as deleted.
        """
        return self.filter(
            sender=user,
            sender_deleted_at__isnull=True,
        )

    def trash_for(self, user):
        """
        Returns all messages that were either received or sent by the given
        user and are marked as deleted.
        """
        return self.filter(
            recipient=user,
            recipient_deleted_at__isnull=False,
        ) | self.filter(
            sender=user,
            sender_deleted_at__isnull=False,
        )

    def conversation_for(self, user):
        return self.filter(conversation__user=user, conversationhead__marked_as_deleted=False)

    def conversations_trash_for(self, user):
        return self.filter(conversation__user=user).filter(conversationhead__marked_as_deleted=True)

    def users_conversation(self, user, conversation):
        return self.filter(Q(sender=user) | Q(recipient=user), conversation=conversation)

    def conversation_heads_for(self, user):
        return self.filter(conversationhead__user=user, conversationhead__marked_as_deleted=False)


@python_2_unicode_compatible
class Message(models.Model):
    """
    A private message from user to user
    """
    subject = models.CharField(_("Subject"), max_length=120)
    body = models.TextField(_("Body"))
    sender = models.ForeignKey(AUTH_USER_MODEL, related_name='sent_messages', verbose_name=_("Sender"))
    recipient = models.ForeignKey(AUTH_USER_MODEL, related_name='received_messages', null=True, blank=True, verbose_name=_("Recipient"))
    parent_msg = models.ForeignKey('self', related_name='next_messages', null=True, blank=True, verbose_name=_("Parent message"))
    sent_at = models.DateTimeField(_("sent at"), null=True, blank=True)
    read_at = models.DateTimeField(_("read at"), null=True, blank=True)
    replied_at = models.DateTimeField(_("replied at"), null=True, blank=True)
    sender_deleted_at = models.DateTimeField(_("Sender deleted at"), null=True, blank=True)
    recipient_deleted_at = models.DateTimeField(_("Recipient deleted at"), null=True, blank=True)
    conversation = models.ForeignKey('Conversation', null=True, blank=True, verbose_name=_('Conversation'))

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

    def get_absolute_url(self):
        return ('messages_detail', [self.id])
    get_absolute_url = models.permalink(get_absolute_url)

    @transaction.atomic
    def save(self, **kwargs):
        updating_conversation = kwargs.pop('update_conversation', False)
        if not self.id:
            self.sent_at = timezone.now()
            creating = True
        else:
            creating = False

        if self.conversation_id:
            # it's an update
            pass
        elif self.parent_msg:
            # it's newly created but has a parent -> belongs to the same conversation
            self.conversation_id = self.parent_msg.conversation_id
        else:
            # it's newly created and has no parents
            conversation = Conversation()
            conversation.save()
            self.conversation_id = conversation.pk

        super(Message, self).save(**kwargs)

        if creating or updating_conversation:
            for user in (self.sender, self.recipient):
                # with multiple recipients ComposeForm causes multiple updates for the sender of a message,
                # this cannot be avoided with reasonable effort
                c, new = ConversationHead.objects.get_or_create(conversation_id=self.conversation_id,
                                                                user=user,
                                                                defaults={'latest_message': self})
                if not new:
                    c.latest_message = self  # warum nicht immer
                    c.mark_as_undeleted()  # warum?
                    c.save()

    class Meta:
        ordering = ['-sent_at']
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")


class ConversationHead(models.Model):
    """
    Points to the latest message in a Conversation.
    There is one ConversationHead per User - this is suboptimal, but inverting the relationship is not an option
    """
    latest_message = models.ForeignKey('Message')
    user = models.ForeignKey(AUTH_USER_MODEL, null=True, blank=True, verbose_name=_("Conversation Owner"))
    conversation = models.ForeignKey('Conversation', related_name='+')
    marked_as_deleted = models.BooleanField(default=False)  # will be set to false if a new message in the conversation is send.

    class Meta:
        unique_together = ('user', 'conversation')

    def __repr__(self):
        return "<id: %s latest_message_id: %s user_id: %s conversation_id: %s, marked_as_deleted: %s>" % (
            self.id,
            self.latest_message_id,
            self.user_id,
            self.conversation_id,
            self.marked_as_deleted,
        )

    @transaction.atomic
    def mark_as_deleted(self):
        """
        deleting a conversation marks all messages that are part of this conversation as deleted for the user
        """
        self.marked_as_deleted = True
        for m in Message.objects.filter(Q(sender=self.user) | Q(recipient=self.user),
                                        conversation=self.conversation):
            now = timezone.now()
            if m.sender == self.user:
                m.sender_deleted_at = now if m.sender_deleted_at is None else m.sender_deleted_at
            else:
                m.recipient_deleted_at = now if m.recipient_deleted_at is None else m.recipient_deleted_at
            m.save()
        self.save()

    @transaction.atomic
    def mark_as_undeleted(self):
        self.marked_as_deleted = False
        for m in Message.objects.filter(Q(sender=self.user) | Q(recipient=self.user),
                                        conversation=self.conversation):
            if m.sender == self.user:
                m.sender_deleted_at = None
            else:
                m.recipient_deleted_at = None
            m.save()
        self.save()


class Conversation(models.Model):
    """
    Foreign keys are pointing to this
    A Conversation 'contains' all messages belonging to one 'thread' -> they all point to the same conversation-object
    """
    pass


def inbox_count_for(user):
    """
    returns the number of unread messages for the given user but does not
    mark them seen
    """
    return Message.objects.filter(recipient=user, read_at__isnull=True, recipient_deleted_at__isnull=True).count()


# fallback for email notification if django-notification could not be found
if "notification" not in settings.INSTALLED_APPS and getattr(settings, 'DJANGO_MESSAGES_NOTIFY', True):
    from django_messages.utils import new_message_email
    signals.post_save.connect(new_message_email, sender=Message)
