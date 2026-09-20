from django.db import migrations


def backfill_conversations(apps, schema_editor):
    Classroom = apps.get_model('classrooms', 'Classroom')
    Group = apps.get_model('groups', 'Group')
    Conversation = apps.get_model('conversations', 'Conversation')

    # Backfill Classroom conversations
    for classroom in Classroom.objects.all():
        Conversation.objects.get_or_create(
            classroom=classroom,
            type='CLASSROOM'
        )

    # Backfill Group conversations
    for group in Group.objects.all():
        Conversation.objects.get_or_create(
            group=group,
            type='GROUP'
        )


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('conversations', '0001_initial'),
        ('classrooms', '0002_jointoken'),
        ('groups', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_conversations, reverse_backfill),
    ]
