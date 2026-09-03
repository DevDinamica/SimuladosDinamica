from django.db import migrations


def ensure_subject(
    Subject,
    code,
    name,
):
    subject = (
        Subject.objects
        .filter(code__iexact=code)
        .first()
    )

    if subject is None:
        subject = (
            Subject.objects
            .filter(name=name)
            .first()
        )

    if subject is None:
        Subject.objects.create(
            code=code,
            name=name,
            is_active=True,
        )
        return

    changed_fields = []

    if subject.code != code:
        subject.code = code
        changed_fields.append("code")

    if subject.name != name:
        subject.name = name
        changed_fields.append("name")

    if not subject.is_active:
        subject.is_active = True
        changed_fields.append("is_active")

    if changed_fields:
        subject.save(
            update_fields=changed_fields,
        )


def ensure_request_catalog(
    apps,
    schema_editor,
):
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
        EducationStage.objects.update_or_create(
            name=(
                "Ensino Fundamental — "
                "Anos Iniciais"
            ),
            defaults={
                "order": 1,
                "is_active": True,
            },
        )
    )

    final_stage, _ = (
        EducationStage.objects.update_or_create(
            name=(
                "Ensino Fundamental — "
                "Anos Finais"
            ),
            defaults={
                "order": 2,
                "is_active": True,
            },
        )
    )

    grades = (
        (
            "EF02",
            initial_stage,
            "2º ano",
            2,
        ),
        (
            "EF05",
            initial_stage,
            "5º ano",
            5,
        ),
        (
            "EF09",
            final_stage,
            "9º ano",
            9,
        ),
    )

    for code, stage, name, order in grades:
        Grade.objects.update_or_create(
            code=code,
            defaults={
                "stage": stage,
                "name": name,
                "order": order,
                "is_active": True,
            },
        )

    ensure_subject(
        Subject,
        code="PORT",
        name="Língua Portuguesa",
    )

    ensure_subject(
        Subject,
        code="MAT",
        name="Matemática",
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "academics",
            "0002_add_initial_year_grades",
        ),
    ]

    operations = [
        migrations.RunPython(
            ensure_request_catalog,
            migrations.RunPython.noop,
        ),
    ]
