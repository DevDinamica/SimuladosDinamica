from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academics.models import AcademicYear, Grade, Subject
from assessments.models import (
    Assessment,
    AssessmentComponent,
    AssessmentVersion,
    Question,
)


class Command(BaseCommand):
    help = (
        "Cadastra a estrutura do Projeto Dinâmico-SAEB "
        "do 9º ano."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            academic_year = AcademicYear.objects.get(
                year=2026,
            )
        except AcademicYear.DoesNotExist:
            raise CommandError(
                "Cadastre primeiro o ano letivo 2026."
            )

        try:
            grade = Grade.objects.get(code="EF09")
        except Grade.DoesNotExist:
            raise CommandError(
                "Cadastre o 9º ano com o código EF09."
            )

        try:
            portuguese = Subject.objects.get(code="PORT")
            mathematics = Subject.objects.get(code="MAT")
        except Subject.DoesNotExist:
            raise CommandError(
                "Cadastre as disciplinas com os códigos "
                "PORT e MAT."
            )

        assessment, created = (
            Assessment.objects.update_or_create(
                code="DIN-SAEB-9-T1-2026",
                defaults={
                    "title": (
                        "Projeto Dinâmico-SAEB — "
                        "Avaliação Diagnóstica I — 9º ano"
                    ),
                    "description": (
                        "Avaliação diagnóstica composta por "
                        "Língua Portuguesa e Matemática."
                    ),
                    "academic_year": academic_year,
                    "subject": None,
                    "instructions": (
                        "Leia cada questão com atenção e marque "
                        "apenas uma alternativa."
                    ),
                    "status": Assessment.Status.DRAFT,
                },
            )
        )

        assessment.grades.add(grade)

        portuguese_component, _ = (
            AssessmentComponent.objects.update_or_create(
                assessment=assessment,
                code="PORT",
                defaults={
                    "subject": portuguese,
                    "title": "Língua Portuguesa",
                    "start_question": 1,
                    "end_question": 20,
                    "order": 1,
                    "is_active": True,
                },
            )
        )

        mathematics_component, _ = (
            AssessmentComponent.objects.update_or_create(
                assessment=assessment,
                code="MAT",
                defaults={
                    "subject": mathematics,
                    "title": "Matemática",
                    "start_question": 21,
                    "end_question": 40,
                    "order": 2,
                    "is_active": True,
                },
            )
        )

        version, _ = AssessmentVersion.objects.update_or_create(
            assessment=assessment,
            code="A",
            defaults={
                "question_count": 40,
                "option_count": 4,
                "total_score": Decimal("10.00"),
                "is_active": True,
            },
        )

        descriptors = {
            1: "D2",
            2: "D15",
            3: "D16",
            4: "D7",
            5: "D11",
            6: "D16",
            7: "D21",
            8: "D5",
            9: "D3",
            10: "D15",
            11: "D4",
            12: "D4",
            13: "D7",
            14: "D8",
            15: "D16",
            16: "D11",
            17: "D3",
            18: "D1",
            19: "D3",
            20: "D4",
            21: "D1",
            22: "D7",
            23: "D34",
            24: "D33",
            25: "D33",
            26: "D1",
            27: "D18",
            28: "D28",
            29: "D8",
            30: "D12",
            31: "D25",
            32: "D20",
            33: "D34",
            34: "D10",
            35: "D15",
            36: "D10",
            37: "D36",
            38: "D28",
            39: "D13",
            40: "D36",
        }

        answers = {
            1: "A",
            2: "D",
            3: "C",
            4: "D",
            # Questão 5 aguardando confirmação pedagógica.
            5: "",
            6: "D",
            7: "B",
            8: "A",
            9: "B",
            10: "A",
            11: "A",
            12: "B",
            13: "B",
            14: "D",
            15: "B",
            16: "B",
            17: "A",
            18: "A",
            19: "B",
            20: "A",
            21: "A",
            22: "B",
            23: "C",
            24: "D",
            25: "C",
            26: "B",
            27: "D",
            28: "C",
            29: "D",
            30: "C",
            31: "C",
            32: "B",
            33: "B",
            34: "A",
            35: "A",
            36: "A",
            37: "C",
            38: "C",
            39: "C",
            40: "A",
        }

        for number in range(1, 41):
            component = (
                portuguese_component
                if number <= 20
                else mathematics_component
            )

            question, _ = Question.objects.update_or_create(
                version=version,
                number=number,
                defaults={
                    "component": component,
                    "descriptor_code": descriptors[number],
                    "correct_answer": answers[number],
                    "weight": Decimal("1.00"),
                    "is_active": True,
                },
            )

            question.full_clean()
            question.save()

        action = "criada" if created else "atualizada"

        self.stdout.write(
            self.style.SUCCESS(
                f"Avaliação {action}: {assessment.code}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "A questão 5 permanece sem resposta até a "
                "confirmação da equipe pedagógica."
            )
        )
