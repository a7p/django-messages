from django.conf.urls import patterns, url
from django.views.generic import RedirectView

from django_messages.views import *

urlpatterns = patterns('',
    url(r'^$', RedirectView.as_view(url='inbox/'), name='messages_redirect'),
    url(r'^inbox/$', inbox, name='messages_inbox'),
    url(r'^outbox/$', outbox, name='messages_outbox'),
    url(r'^conversations/$', conversations, name='messages_conversations'),
    url(r'^conversations_trash/$', conversations_trash, name='messages_conversations_trash'),
    url(r'^compose/$', compose, name='messages_compose'),
    url(r'^compose/(?P<recipient>[\w.@+-]+)/$', compose, name='messages_compose_to'),
    url(r'^reply/(?P<message_id>[\d]+)/$', reply, name='messages_reply'),
    url(r'^view/(?P<message_id>[\d]+)/$', view, name='messages_detail'),
    url(r'^conversation_view/(?P<conversation_id>[\w\-]+)/$', conversation_view, name='messages_conversation_detail'),
    url(r'^delete/(?P<message_id>[\d]+)/$', delete, name='messages_delete'),
    url(r'^undelete/(?P<message_id>[\d]+)/$', undelete, name='messages_undelete'),
    url(r'^delete_conversation/(?P<conversation_id>[\w\-]+)/$', delete_conversation, name='messages_delete_conversation'),
    url(r'^undelete_conversation/(?P<conversation_id>[\w\-]+)/$', undelete_conversation, name='messages_undelete_conversation'),
    url(r'^trash/$', trash, name='messages_trash'),
)
