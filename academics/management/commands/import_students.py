import csv
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academics.models import Classroom, Enrollment, Student
from institutions.models import School


class Command(BaseCommand):
    help = "Importa alunos e matrículas a partir de um arquivo CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Caminho do arquivo CSV.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = Path(options["csv_file"])

        if not csv_path.exists():
            raise CommandError(
                f"Arquivo não encontrado: {csv_path}"
            )

        created_students = 0
        updated_students = 0
        created_enrollments = 0

        with csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            required_columns = {
                "school_id",
                "classroom_id",
                "registration_code",
                "full_name",
            }

            available_columns = set(reader.fieldnames or [])
            missing_columns = required_columns - available_columns

            if missing_columns:
                missing = ", ".join(sorted(missing_columns))

                raise CommandError(
                    f"Colunas obrigatórias ausentes: {missing}"
                )

            for row_number, row in enumerate(reader, start=2):
                try:
                    school = School.objects.get(
                        pk=row["school_id"].strip()
                    )
                    classroom = Classroom.objects.get(
                        pk=row["classroom_id"].strip()
                    )
                except School.DoesNotExist:
                    raise CommandError(
                        f"Linha {row_number}: escola não encontrada."
                    )
                except Classroom.DoesNotExist:
                    raise CommandError(
                        f"Linha {row_number}: turma não encontrada."
                    )

                if classroom.school_id != school.id:
                    raise CommandError(
                        f"Linha {row_number}: a turma não pertence "
                        "à escola informada."
                    )

                registration_code = row[
                    "registration_code"
                ].strip()
                full_name = row["full_name"].strip()

                if not registration_code or not full_name:
                    raise CommandError(
                        f"Linha {row_number}: matrícula e nome "
                        "são obrigatórios."
                    )

                birth_date = None
                birth_date_value = row.get(
                    "birth_date",
                    "",
                ).strip()

                if birth_date_value:
                    try:
                        birth_date = datetime.strptime(
                            birth_date_value,
                            "%Y-%m-%d",
                        ).date()
                    except ValueError:
                        raise CommandError(
                            f"Linha {row_number}: data inválida. "
                            "Utilize AAAA-MM-DD."
                        )

                student, created = Student.objects.update_or_create(
                    school=school,
                    registration_code=registration_code,
                    defaults={
                        "full_name": full_name,
                        "birth_date": birth_date,
                        "responsible_name": row.get(
                            "responsible_name",
                            "",
                        ).strip(),
                        "responsible_phone": row.get(
                            "responsible_phone",
                            "",
                        ).strip(),
                        "is_active": True,
                    },
                )

                if created:
                    created_students += 1
                else:
                    updated_students += 1

                _, enrollment_created = (
                    Enrollment.objects.get_or_create(
                        student=student,
                        classroom=classroom,
                        defaults={
                            "status": Enrollment.Status.ACTIVE,
                        },
                    )
                )

                if enrollment_created:
                    created_enrollments += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Importação concluída: "
                f"{created_students} alunos criados, "
                f"{updated_students} atualizados e "
                f"{created_enrollments} matrículas criadas."
            )
        )
