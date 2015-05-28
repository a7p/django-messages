# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('django_messages', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='conversation_id',
            field=models.CharField(default='', verbose_name='Conversation ID', max_length=36, editable=False),
            preserve_default=False,
        ),
    ]
