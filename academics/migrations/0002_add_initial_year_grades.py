from django.db import migrations


def add_initial_year_grades(apps, schema_editor):
    EducationStage = apps.get_model(
        "academics",
        "EducationStage",
    )
    Grade = apps.get_model(
        "academics",
        "Grade",
    )
    Subject = apps.get_model(
        "academics",
        "Subject",
    )

    initial_stage, _ = (
        EducationStage.objects.get_or_create(
            name="Ensino Fundamental — Anos Iniciais",
            defaults={
                "order": 1,
                "is_active": True,
            },
        )
    )

    Grade.objects.update_or_create(
        code="EF02",
        defaults={
            "stage": initial_stage,
            "name": "2º ano",
            "order": 2,
            "is_active": True,
        },
    )

    Grade.objects.update_or_create(
        code="EF05",
        defaults={
            "stage": initial_stage,
            "name": "5º ano",
            "order": 5,
            "is_active": True,
        },
    )

    Subject.objects.filter(
        code="hist",
        name="Histótia",
    ).update(
        name="História",
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "academics",
            "0001_initial",
        ),
    ]

    operations = [
        migrations.RunPython(
            add_initial_year_grades,
            migrations.RunPython.noop,
        ),
    ]