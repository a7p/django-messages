import datetime
from django.db.models import Q, Max, F
from django.test import TestCase, override_settings
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.utils import timezone
from django_messages.forms import ComposeForm
from django_messages.models import Message, Conversation
from django_messages.utils import format_subject, format_quote
from django.conf import settings
from .utils import get_user_model

User = get_user_model()


class SendTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            'user1', 'user1@example.com', '123456')
        self.user2 = User.objects.create_user(
            'user2', 'user2@example.com', '123456')
        self.msg1 = Message(sender=self.user1, recipient=self.user2,
                            subject='Subject Text', body='Body Text')
        self.msg1.save()

    def testBasic(self):
        self.assertEqual(self.msg1.sender, self.user1)
        self.assertEqual(self.msg1.recipient, self.user2)
        self.assertEqual(self.msg1.subject, 'Subject Text')
        self.assertEqual(self.msg1.body, 'Body Text')
        self.assertEqual(self.user1.sent_messages.count(), 1)
        self.assertEqual(self.user1.received_messages.count(), 0)
        self.assertEqual(self.user2.received_messages.count(), 1)
        self.assertEqual(self.user2.sent_messages.count(), 0)

    def test_conversation_id_is_generated(self):
        self.assertEqual(len(str(self.msg1.conversation_id)), 36)

    def test_conversion_id_differs_between_messages(self):
        self.msg2 = Message(sender=self.user1, recipient=self.user2,
                            subject='Other Subject', body='Body Text')
        self.msg2.save()
        self.assertNotEqual(self.msg1.conversation_id, self.msg2.conversation_id,
                            'Every non-reply message should get a different conversation id')

    def test_conversion_id_on_replies_is_the_same_as_in_the_message_replied_to(self):
        self.msg2 = Message(sender=self.user1, recipient=self.user2,
                            subject='Subject Text', body='Body Text', parent_msg=self.msg1)
        self.msg2.save()
        self.assertEqual(self.msg1.conversation_id, self.msg2.conversation_id, "The conversion id of a reply should be equal to the original one")


class DeleteTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            'user3', 'user3@example.com', '123456')
        self.user2 = User.objects.create_user(
            'user4', 'user4@example.com', '123456')
        self.msg1 = Message(sender=self.user1, recipient=self.user2,
                            subject='Subject Text 1', body='Body Text 1')
        self.msg2 = Message(sender=self.user1, recipient=self.user2,
                            subject='Subject Text 2', body='Body Text 2')
        self.msg1.sender_deleted_at = timezone.now()
        self.msg2.recipient_deleted_at = timezone.now()
        self.msg1.save()
        self.msg2.save()

    def testBasic(self):
        self.assertEqual(Message.objects.outbox_for(self.user1).count(), 1)
        self.assertEqual(
            Message.objects.outbox_for(self.user1)[0].subject,
            'Subject Text 2'
        )
        self.assertEqual(Message.objects.inbox_for(self.user2).count(), 1)
        self.assertEqual(
            Message.objects.inbox_for(self.user2)[0].subject,
            'Subject Text 1'
        )
        #undelete
        self.msg1.sender_deleted_at = None
        self.msg2.recipient_deleted_at = None
        self.msg1.save()
        self.msg2.save()
        self.assertEqual(Message.objects.outbox_for(self.user1).count(), 2)
        self.assertEqual(Message.objects.inbox_for(self.user2).count(), 2)


class IntegrationTestCase(TestCase):
    """
    Test the app from a user perpective using Django's Test-Client.
    """

    T_USER_DATA = [{'username': 'user_1', 'password': '123456',
                    'email': 'user_1@example.com'},
                   {'username': 'user_2', 'password': '123456',
                    'email': 'user_2@example.com'}]
    T_MESSAGE_DATA = [{'subject': 'Test Subject 1',
                       'body': 'Lorem ipsum\ndolor sit amet\n\nconsectur.'}]

    def setUp(self):
        """ create 2 users and a test-client logged in as user_1 """
        self.user_1 = User.objects.create_user(**self.T_USER_DATA[0])
        self.user_2 = User.objects.create_user(**self.T_USER_DATA[1])
        self.c = Client()
        self.c.login(username=self.T_USER_DATA[0]['username'],
                     password=self.T_USER_DATA[0]['password'])

    def testInboxEmpty(self):
        """ request the empty inbox """
        response = self.c.get(reverse('messages_inbox'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name,
                         'django_messages/inbox.html')
        self.assertEqual(len(response.context['message_list']), 0)

    def testOutboxEmpty(self):
        """ request the empty outbox """
        response = self.c.get(reverse('messages_outbox'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name,
                         'django_messages/outbox.html')
        self.assertEqual(len(response.context['message_list']), 0)

    def testTrashEmpty(self):
        """ request the empty trash """
        response = self.c.get(reverse('messages_trash'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name,
                         'django_messages/trash.html')
        self.assertEqual(len(response.context['message_list']), 0)

    def testCompose(self):
        """ compose a message step by step """
        response = self.c.get(reverse('messages_compose'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name,
                         'django_messages/compose.html')
        response = self.c.post(
            reverse('messages_compose'),
            {
                'recipient': self.T_USER_DATA[1]['username'],
                'subject': self.T_MESSAGE_DATA[0]['subject'],
                'body': self.T_MESSAGE_DATA[0]['body']
            })
        # successfull sending should redirect to inbox
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'],
                         "http://testserver%s" % reverse('messages_inbox'))

        # make sure the message exists in the outbox after sending
        response = self.c.get(reverse('messages_outbox'))
        self.assertEqual(len(response.context['message_list']), 1)

    def testReply(self):
        """ test that user_2 can reply """
        # create a message for this test
        Message.objects.create(sender=self.user_1,
                               recipient=self.user_2,
                               subject=self.T_MESSAGE_DATA[0]['subject'],
                               body=self.T_MESSAGE_DATA[0]['body'])
        # log the user_2 in and check the inbox
        self.c.login(username=self.T_USER_DATA[1]['username'],
                     password=self.T_USER_DATA[1]['password'])
        response = self.c.get(reverse('messages_inbox'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name,
                         'django_messages/inbox.html')
        self.assertEqual(len(response.context['message_list']), 1)
        pk = getattr(response.context['message_list'][0], 'pk')
        # reply to the first message
        response = self.c.get(reverse('messages_reply',
                              kwargs={'message_id': pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name,
                         'django_messages/compose.html')
        self.assertEqual(
            response.context['form'].initial['body'],
            format_quote(self.user_1, self.T_MESSAGE_DATA[0]['body'])
        )
        self.assertEqual(
            response.context['form'].initial['subject'],
            u"Re: %(subject)s" % {'subject': self.T_MESSAGE_DATA[0]['subject']}
        )

    @override_settings(DJANGO_MESSAGES_PAGINATE_BY=1)
    def test_pagination_inbox(self):
        self.assertEqual(settings.DJANGO_MESSAGES_PAGINATE_BY, 1)
        for r in range(2):
            Message.objects.create(sender=self.user_1,
                           recipient=self.user_2,
                           subject=self.T_MESSAGE_DATA[0]['subject'],
                           body=self.T_MESSAGE_DATA[0]['body'])

        self.c.login(username=self.T_USER_DATA[1]['username'],
                     password=self.T_USER_DATA[1]['password'])

        resp = self.c.get(reverse('messages_inbox'))
        self.assertIn('message_list_page', resp.context)
        self.assertTrue(resp.context['message_list_page'].has_next())
        self.assertFalse(resp.context['message_list_page'].has_previous())

        resp = self.c.get("{}?page=2".format(reverse('messages_inbox')))
        self.assertIn('message_list_page', resp.context)
        self.assertTrue(resp.context['message_list_page'].has_previous())
        self.assertFalse(resp.context['message_list_page'].has_next())

    @override_settings(DJANGO_MESSAGES_PAGINATE_BY=1)
    def test_pagination_outbox(self):
        self.assertEqual(settings.DJANGO_MESSAGES_PAGINATE_BY, 1)
        for r in range(2):
            Message.objects.create(sender=self.user_1,
                           recipient=self.user_2,
                           subject=self.T_MESSAGE_DATA[0]['subject'],
                           body=self.T_MESSAGE_DATA[0]['body'])

        resp = self.c.get(reverse('messages_outbox'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('message_list_page', resp.context)
        self.assertTrue(resp.context['message_list_page'].has_next())
        self.assertFalse(resp.context['message_list_page'].has_previous())

        resp = self.c.get("{}?page=2".format(reverse('messages_outbox')))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('message_list_page', resp.context)
        self.assertTrue(resp.context['message_list_page'].has_previous())
        self.assertFalse(resp.context['message_list_page'].has_next())

    @override_settings(DJANGO_MESSAGES_PAGINATE_BY=1)
    def test_pagination_trash(self):
        self.assertEqual(settings.DJANGO_MESSAGES_PAGINATE_BY, 1)
        for r in range(2):
            Message.objects.create(sender=self.user_1,
                           recipient=self.user_2,
                           subject=self.T_MESSAGE_DATA[0]['subject'],
                           body=self.T_MESSAGE_DATA[0]['body'],
                           sender_deleted_at=timezone.now())

        resp = self.c.get(reverse('messages_trash'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('message_list_page', resp.context)
        self.assertTrue(resp.context['message_list_page'].has_next())
        self.assertFalse(resp.context['message_list_page'].has_previous())

        resp = self.c.get("{}?page=2".format(reverse('messages_trash')))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('message_list_page', resp.context)
        self.assertTrue(resp.context['message_list_page'].has_previous())
        self.assertFalse(resp.context['message_list_page'].has_next())


class TestOrmBehavior(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            'user1', 'user1@example.com', '123456')
        self.user2 = User.objects.create_user(
            'user2', 'user2@example.com', '123456')

        parent_msg = None
        for n in range(10):
            user_a, user_b = (self.user1, self.user2) if n % 2 else (self.user2, self.user1)
            m = Message.objects.create(sender=user_a,
                           recipient=user_b,
                           subject="{}: {}".format(n, " subject"),
                           body="{}: {}".format(n, " body"),
                           sent_at=timezone.now() - datetime.timedelta(days=100) + datetime.timedelta(seconds=10) * n,
                           parent_msg=parent_msg)
            m.save()
            self.newest_msg1 = m
            parent_msg = m

        for n in range(10):
            user_a, user_b = (self.user1, self.user2) if n % 2 else (self.user2, self.user1)
            m = Message.objects.create(sender=user_a,
                           recipient=user_b,
                           subject="{}: {}".format(n, " subject"),
                           body="{}: {}".format(n, " body"),
                           sent_at=timezone.now() - datetime.timedelta(days=100) + datetime.timedelta(seconds=10) * n)
            m.save()
            self.newest_msg2 = m

    def test_distinct_group_by_combination(self):
        pass
        # self.assertEqual(Message.objects.order_by('conversation_id', '-sent_at').distinct('conversation_id').count(), 11)  # ze Posgres version
        # conversation_ids = Message.objects.filter(Q(sender=self.user1) | Q(recipient=self.user1)).values('conversation_id').distinct()
        # conversation_ids = Message.objects.filter(Q(sender=self.user1) | Q(recipient=self.user1)).annotate(most_recent=Max('sent_at'))
        # conversation_ids = Message.objects.filter(Q(sender=self.user1) | Q(recipient=self.user1)).values('conversation_id').order_by().distinct()
        # conversation_ids = [elem['conversation_id'] for elem in conversation_ids]
        # self.assertEqual(conversation_ids.count(), 11)
        # self.assertEqual(len(conversation_ids), 11)
        # conversation_ids = [c['conversation_id'] for c in conversation_ids]
        # ms = Message.objects.filter(conversation_id__in=conversation_ids)
        # res = set()
        # for id_ in conversation_ids:
        #     newest = Message.objects.filter(conversation_id=id_).order_by('-sent_at').first()
        #     newest2 = Message.objects.filter(conversation_id=id_).latest('sent_at')
            # newest2 = Message.objects.filter(conversation_id=id_).aggregate(Max('sent_at'))
            # self.assertEqual(newest, newest2)
            # res.add(newest)

        # res2 = Message.objects.annotate(max_date=Max('sent_at')).filter(sent_at=F('max_date'))
        # self.assertEqual(conversation_ids, 0)
        # q = 'SELECT * FROM django_messages_message WHERE conversation_id IN ("1","2","3","4") GROUP BY conversation_id HAVING MAX(sent_at)', [conversation_ids[0],]
        # res2 = Message.objects.raw(q)
        # for p in res2:
        #     self.assertEqual(p, 10)
        # self.assertEqual(res2, 11)
        # newest = Message.objects.filter(Q(sender=self.user1) | Q(recipient=self.user1)).filter(conversation_ids__in=conversation_ids)
        # self.assertEqual(len(conversation_ids), 11)


class TestConversation(TestCase):
    def setUp(self):
        self.user1, self.user2, self.user3 = User.objects.create_user('user1', 'user1@example.com', '123456'),\
                                             User.objects.create_user('user2', 'user2@example.com', '123456'),\
                                             User.objects.create_user('user3', 'user3@example.com', '123456')

    def test_conversation_is_updated(self):
        """There should be only one Conversion Object for each user for each conversation.
        The Conversion should always be updated to the latest message with which the user had contact (either as
        recipient or as sender)
        """
        parent_msg = None
        for n in range(20):
            user_a, user_b, user_c = (self.user1, self.user2, self.user3) if n % 3 else (self.user2, self.user1, self.user3)
            f = ComposeForm({"recipient":[user_b, user_c],
                            "subject":'asdf',
                            "body":'bsdf'}
                            )
            f.is_valid()
            m = f.save(user_a, parent_msg=parent_msg)
            parent_msg = m[-1]
            user_a.latest = m[-1].sent_at
            user_a.conversation_id = m[-1].conversation_id

        self.assertEqual(Conversation.objects.all().count(), 3)
        self.assertEqual(Conversation.objects.get(user=user_a, conversation_id=user_a.conversation_id)\
                         .latest_message.sent_at, user_a.latest)


class FormatTestCase(TestCase):
    """ some tests for helper functions """
    def testSubject(self):
        """ test that reply counting works as expected """
        self.assertEqual(format_subject(u"foo bar"), u"Re: foo bar")
        self.assertEqual(format_subject(u"Re: foo bar"), u"Re[2]: foo bar")
        self.assertEqual(format_subject(u"Re[2]: foo bar"), u"Re[3]: foo bar")
        self.assertEqual(format_subject(u"Re[10]: foo bar"),
                         u"Re[11]: foo bar")
