# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('django_messages', '0002_auto_20150608_1156'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConversationHead',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('marked_as_deleted', models.BooleanField(default=False)),
                ('conversation', models.ForeignKey(related_name='+', to='django_messages.Conversation')),
                ('latest_message', models.ForeignKey(to='django_messages.Message')),
                ('user', models.ForeignKey(verbose_name='Conversation Owner', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='conversationhead',
            unique_together=set([('user', 'conversation')]),
        ),
        migrations.RemoveField(
            model_name='message',
            name='conversation_id',
        ),
        migrations.AddField(
            model_name='message',
            name='conversation',
            field=models.ForeignKey(verbose_name='Conversation', blank=True, to='django_messages.Conversation', null=True),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='conversation',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='conversation',
            name='user',
        ),
        migrations.RemoveField(
            model_name='conversation',
            name='marked_as_deleted',
        ),
        migrations.RemoveField(
            model_name='conversation',
            name='latest_message',
        ),
        migrations.RemoveField(
            model_name='conversation',
            name='conversation_id',
        ),
    ]
