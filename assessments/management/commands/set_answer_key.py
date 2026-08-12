from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from assessments.models import AssessmentVersion, Question


class Command(BaseCommand):
    help = "Cadastra ou atualiza o gabarito de uma versão."

    def add_arguments(self, parser):
        parser.add_argument(
            "version_id",
            type=int,
            help="ID da versão da prova.",
        )
        parser.add_argument(
            "answers",
            type=str,
            help="Respostas. Exemplo: ABCDEACBDA",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            version = AssessmentVersion.objects.get(
                pk=options["version_id"],
            )
        except AssessmentVersion.DoesNotExist:
            raise CommandError("Versão não encontrada.")

        answers = (
            options["answers"]
            .replace(" ", "")
            .replace(",", "")
            .replace(";", "")
            .upper()
        )

        if len(answers) != version.question_count:
            raise CommandError(
                f"A versão possui {version.question_count} questões, "
                f"mas foram recebidas {len(answers)} respostas."
            )

        allowed_answers = set(
            "ABCDE"[: version.option_count]
        )

        invalid_answers = sorted(
            set(answers) - allowed_answers
        )

        if invalid_answers:
            invalid = ", ".join(invalid_answers)

            raise CommandError(
                f"Alternativas inválidas: {invalid}."
            )

        for number, answer in enumerate(answers, start=1):
            question, _ = Question.objects.update_or_create(
                version=version,
                number=number,
                defaults={
                    "correct_answer": answer,
                    "is_active": True,
                },
            )

            question.full_clean()
            question.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Gabarito da versão {version.code} cadastrado: "
                f"{version.question_count} questões."
            )
        )
