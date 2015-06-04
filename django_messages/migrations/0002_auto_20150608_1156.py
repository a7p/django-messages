# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('django_messages', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Conversation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('conversation_id', models.CharField(verbose_name='Conversation ID', max_length=36, editable=False)),
                ('marked_as_deleted', models.BooleanField(default=False)),
                ('latest_message', models.ForeignKey(to='django_messages.Message')),
                ('user', models.ForeignKey(verbose_name='Conversation Owner', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='conversation',
            unique_together=set([('user', 'conversation_id')]),
        ),
        migrations.AddField(
            model_name='message',
            name='conversation_id',
            field=models.CharField(default='', verbose_name='Conversation ID', max_length=36, editable=False),
            preserve_default=False,
        ),
    ]
