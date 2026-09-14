import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "applications",
            "0006_link_answer_sheet_to_participation_card",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="answersheet",
            name="participation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="answer_sheets",
                to="applications.participation",
                verbose_name="participação",
            ),
        ),
        migrations.AlterField(
            model_name="answersheet",
            name="participation_card",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="answer_sheet",
                to="applications.participationcard",
                verbose_name="cartão disciplinar",
            ),
        ),
    ]