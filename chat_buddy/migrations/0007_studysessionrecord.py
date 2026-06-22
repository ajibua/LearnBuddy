import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat_buddy', '0006_flashcarddeck_flashcard_quiz_quizquestion'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StudySessionRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity_type', models.CharField(max_length=20)),
                ('duration_seconds', models.IntegerField(default=0)),
                ('date', models.DateField(default=django.utils.timezone.now)),
                ('study_material', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='study_sessions', to='chat_buddy.studymaterial')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='study_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date'],
            },
        ),
    ]
