from pathlib import Path

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from applications.answer_sheets import (
    generate_answer_sheets_pdf,
)
from applications.models import (
    Participation,
    SimulationApplication,
)


class Command(BaseCommand):
    help = "Gera os cartões-resposta de uma aplicação."

    def add_arguments(self, parser):
        parser.add_argument(
            "application_code",
            type=str,
            help="Código da aplicação.",
        )
        parser.add_argument(
            "output_file",
            type=str,
            help="Caminho do PDF de saída.",
        )

    def handle(self, *args, **options):
        application_code = options[
            "application_code"
        ]
        output_path = Path(
            options["output_file"]
        )

        try:
            application = (
                SimulationApplication.objects.get(
                    code=application_code,
                )
            )
        except SimulationApplication.DoesNotExist:
            raise CommandError(
                "Aplicação não encontrada."
            )

        participations = (
            application.participations.exclude(
                status=Participation.Status.CANCELLED,
            )
            .select_related(
                "application",
                "application__municipality",
                "student",
                "assessment_version",
                "application_classroom__classroom",
                (
                    "application_classroom__"
                    "classroom__school"
                ),
                (
                    "application_classroom__"
                    "classroom__grade"
                ),
            )
            .order_by(
                "application_classroom__classroom__school__name",
                "application_classroom__classroom__name",
                "student__full_name",
            )
        )

        if not participations.exists():
            raise CommandError(
                "A aplicação não possui participações."
            )

        pdf = generate_answer_sheets_pdf(
            participations
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_bytes(
            pdf.getvalue()
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{participations.count()} cartão(ões) "
                f"gerado(s): {output_path}"
            )
        )
