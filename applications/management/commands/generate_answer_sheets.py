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
    ParticipationCard,
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

        cards = (
            ParticipationCard.objects
            .filter(
                participation__application=(
                    application
                ),
                application_assessment__is_active=True,
            )
            .exclude(
                participation__status=(
                    Participation.Status.CANCELLED
                ),
            )
            .exclude(
                status=(
                    ParticipationCard.Status.CANCELLED
                ),
            )
            .select_related(
                "participation",
                "participation__application",
                (
                    "participation__"
                    "application__municipality"
                ),
                "participation__student",
                (
                    "participation__"
                    "application_classroom__classroom"
                ),
                (
                    "participation__"
                    "application_classroom__"
                    "classroom__school"
                ),
                (
                    "participation__"
                    "application_classroom__"
                    "classroom__grade"
                ),
                "application_assessment",
                (
                    "application_assessment__"
                    "assessment"
                ),
                (
                    "application_assessment__"
                    "assessment__subject"
                ),
                "assessment_version",
            )
            .order_by(
                (
                    "participation__"
                    "application_classroom__"
                    "classroom__school__name"
                ),
                (
                    "participation__"
                    "application_classroom__"
                    "classroom__name"
                ),
                "participation__student__full_name",
                "application_assessment__order",
            )
        )

        if not cards.exists():
            raise CommandError(
                "A aplicação não possui cartões disciplinares."
            )

        pdf = generate_answer_sheets_pdf(
            cards
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
                f"{cards.count()} cartão(ões) "
                f"gerado(s): {output_path}"
            )
        )
