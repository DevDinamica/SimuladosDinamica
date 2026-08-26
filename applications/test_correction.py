from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError

from academics.models import (
    AcademicYear,
    Classroom,
    EducationStage,
    Enrollment,
    Grade,
    Student,
    Subject,
)
from assessments.models import (
    Assessment,
    AssessmentComponent,
    AssessmentVersion,
    Question,
)
from institutions.models import Municipality, School

from applications.correction import (
    initialize_answer_sheet,
    process_answer_sheet,
)
from applications.models import (
    AnswerEntry,
    AnswerSheet,
    AnswerSheetBreakdown,
    ApplicationClassroom,
    Participation,
    SimulationApplication,
)

from types import SimpleNamespace
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from applications.admin import (
    AnswerSheetAdmin,
    ParticipationAdmin,
    SimulationApplicationAdmin,
)

class CorrectionServiceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = (
            get_user_model().objects.create_superuser(
                username="admin-testes",
                email="admin-testes@example.com",
                password="senha-testes-123",
            )
        )
                
        cls.municipality = Municipality.objects.create(
            name="Fortaleza",
            state="CE",
            ibge_code="2304400",
        )

        cls.school = School.objects.create(
            municipality=cls.municipality,
            name="Escola de Testes",
            inep_code="23000001",
        )

        cls.academic_year = AcademicYear.objects.create(
            year=2026,
            is_current=True,
        )

        cls.stage = EducationStage.objects.create(
            name="Ensino Fundamental",
            order=1,
        )

        cls.grade = Grade.objects.create(
            stage=cls.stage,
            name="9º ano",
            code="EF9",
            order=9,
        )

        cls.subject = Subject.objects.create(
            name="Matemática",
            code="MAT",
        )

        cls.classroom = Classroom.objects.create(
            school=cls.school,
            academic_year=cls.academic_year,
            grade=cls.grade,
            name="A",
            shift=Classroom.Shift.MORNING,
        )
        cls.classroom.subjects.add(cls.subject)

        cls.student = Student.objects.create(
            school=cls.school,
            registration_code="TESTE-001",
            full_name="Aluna de Teste",
        )

        cls.enrollment = Enrollment.objects.create(
            student=cls.student,
            classroom=cls.classroom,
            status=Enrollment.Status.ACTIVE,
        )

        cls.assessment = Assessment.objects.create(
            title="Prova Automatizada",
            code="PROVA-TESTE-2026",
            academic_year=cls.academic_year,
            subject=cls.subject,
            status=Assessment.Status.PUBLISHED,
        )
        cls.assessment.grades.add(cls.grade)

        cls.component = AssessmentComponent.objects.create(
            assessment=cls.assessment,
            subject=cls.subject,
            code="MAT",
            title="Matemática",
            start_question=1,
            end_question=4,
            order=1,
        )

        cls.version = AssessmentVersion.objects.create(
            assessment=cls.assessment,
            code="A",
            question_count=4,
            option_count=4,
            total_score=Decimal("10.00"),
        )

        cls.question_1 = Question.objects.create(
            version=cls.version,
            component=cls.component,
            number=1,
            descriptor_code="RT01",
            descriptor="Raciocínio técnico",
            correct_answer=Question.Answer.A,
            weight=Decimal("1.00"),
        )

        cls.question_2 = Question.objects.create(
            version=cls.version,
            component=cls.component,
            number=2,
            descriptor_code="RT01",
            descriptor="Raciocínio técnico",
            correct_answer=Question.Answer.B,
            weight=Decimal("1.00"),
        )

        cls.question_3 = Question.objects.create(
            version=cls.version,
            component=cls.component,
            number=3,
            descriptor_code="IN01",
            descriptor="Interpretação de dados",
            correct_answer=Question.Answer.C,
            weight=Decimal("2.00"),
        )

        cls.question_4 = Question.objects.create(
            version=cls.version,
            component=cls.component,
            number=4,
            descriptor_code="IN01",
            descriptor="Interpretação de dados",
            correct_answer=Question.Answer.D,
            weight=Decimal("1.00"),
        )

        cls.application = SimulationApplication.objects.create(
            title="Aplicação Automatizada",
            assessment=cls.assessment,
            municipality=cls.municipality,
            application_date=date(2026, 9, 10),
            status=SimulationApplication.Status.READY,
        )

        cls.application_classroom = (
            ApplicationClassroom.objects.create(
                application=cls.application,
                classroom=cls.classroom,
                room_name="Sala 01",
            )
        )

        cls.participation = Participation.objects.create(
            application=cls.application,
            application_classroom=cls.application_classroom,
            student=cls.student,
            enrollment=cls.enrollment,
            assessment_version=cls.version,
        )

    def get_participation(self):
        return Participation.objects.get(
            pk=self.participation.pk
        )

    def get_admin_request(self):
        request = RequestFactory().post(
            "/admin/applications/"
        )
        request.user = self.admin_user

        return request

    def initialize(self):
        return initialize_answer_sheet(
            self.get_participation()
        )[0]

    def get_answers(self, answer_sheet):
        return list(
            answer_sheet.answers
            .select_related(
                "question",
                "question__version",
            )
            .order_by("question__number")
        )

    def mark_single(self, answer, selected_answer):
        answer.marking_status = (
            AnswerEntry.MarkingStatus.SINGLE
        )
        answer.selected_answer = selected_answer
        answer.save()

    def test_initialization_creates_sheet_and_answers(self):
        answer_sheet, created = initialize_answer_sheet(
            self.get_participation()
        )

        self.assertTrue(created)
        self.assertEqual(
            answer_sheet.status,
            AnswerSheet.Status.DRAFT,
        )
        self.assertEqual(answer_sheet.question_count, 4)
        self.assertEqual(answer_sheet.answers.count(), 4)
        self.assertEqual(
            answer_sheet.answers.filter(
                marking_status=(
                    AnswerEntry.MarkingStatus.BLANK
                )
            ).count(),
            4,
        )

    def test_initialization_is_idempotent(self):
        first_sheet, first_created = (
            initialize_answer_sheet(
                self.get_participation()
            )
        )
        second_sheet, second_created = (
            initialize_answer_sheet(
                self.get_participation()
            )
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_sheet.pk, second_sheet.pk)
        self.assertEqual(AnswerSheet.objects.count(), 1)
        self.assertEqual(AnswerEntry.objects.count(), 4)

    def test_blank_sheet_is_processed(self):
        answer_sheet = process_answer_sheet(
            self.initialize()
        )

        self.assertEqual(
            answer_sheet.status,
            AnswerSheet.Status.PROCESSED,
        )
        self.assertEqual(answer_sheet.answered_count, 0)
        self.assertEqual(answer_sheet.correct_count, 0)
        self.assertEqual(answer_sheet.incorrect_count, 0)
        self.assertEqual(answer_sheet.blank_count, 4)
        self.assertEqual(answer_sheet.multiple_count, 0)
        self.assertEqual(
            answer_sheet.score,
            Decimal("0.00"),
        )
        self.assertEqual(
            answer_sheet.percentage,
            Decimal("0.00"),
        )

        participation = self.get_participation()

        self.assertEqual(
            participation.status,
            Participation.Status.PROCESSED,
        )

    def test_correct_incorrect_blank_and_multiple(self):
        answer_sheet = self.initialize()
        answers = self.get_answers(answer_sheet)

        self.mark_single(
            answers[0],
            answers[0].question.correct_answer,
        )

        self.mark_single(
            answers[1],
            Question.Answer.A,
        )

        answers[2].marking_status = (
            AnswerEntry.MarkingStatus.MULTIPLE
        )
        answers[2].selected_answer = ""
        answers[2].save()

        answer_sheet = process_answer_sheet(
            answer_sheet
        )

        self.assertEqual(answer_sheet.correct_count, 1)
        self.assertEqual(answer_sheet.incorrect_count, 1)
        self.assertEqual(answer_sheet.blank_count, 1)
        self.assertEqual(answer_sheet.multiple_count, 1)
        self.assertEqual(answer_sheet.answered_count, 2)

        self.assertEqual(
            (
                answer_sheet.correct_count
                + answer_sheet.incorrect_count
                + answer_sheet.blank_count
                + answer_sheet.multiple_count
            ),
            answer_sheet.question_count,
        )

    def test_question_weight_changes_score(self):
        answer_sheet = self.initialize()
        answers = self.get_answers(answer_sheet)

        self.mark_single(
            answers[2],
            answers[2].question.correct_answer,
        )

        answer_sheet = process_answer_sheet(
            answer_sheet
        )

        self.assertEqual(answer_sheet.correct_count, 1)
        self.assertEqual(
            answer_sheet.score,
            Decimal("4.00"),
        )
        self.assertEqual(
            answer_sheet.percentage,
            Decimal("40.00"),
        )

    def test_incomplete_answer_key_prevents_processing(self):
        Question.objects.filter(
            pk=self.question_2.pk,
        ).update(
            correct_answer="",
        )

        answer_sheet = self.initialize()

        with self.assertRaisesMessage(
            ValidationError,
            "O gabarito está incompleto",
        ):
            process_answer_sheet(answer_sheet)

        answer_sheet.refresh_from_db()

        self.assertEqual(
            answer_sheet.status,
            AnswerSheet.Status.DRAFT,
        )
        self.assertEqual(
            answer_sheet.answers.exclude(
                is_correct=None,
            ).count(),
            0,
        )

    def test_missing_active_question_prevents_initialization(self):
        Question.objects.filter(
            pk=self.question_4.pk,
        ).update(
            is_active=False,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "espera 4 questões",
        ):
            initialize_answer_sheet(
                self.get_participation()
            )

        self.assertFalse(
            AnswerSheet.objects.exists()
        )

    def test_missing_answer_prevents_processing(self):
        answer_sheet = self.initialize()

        answer_sheet.answers.order_by(
            "question__number"
        ).last().delete()

        with self.assertRaisesMessage(
            ValidationError,
            "deveria possuir 4",
        ):
            process_answer_sheet(answer_sheet)

        answer_sheet.refresh_from_db()

        self.assertEqual(
            answer_sheet.status,
            AnswerSheet.Status.DRAFT,
        )

    def test_absent_participation_is_rejected(self):
        participation = self.get_participation()
        participation.status = Participation.Status.ABSENT
        participation.save()

        with self.assertRaisesMessage(
            ValidationError,
            "aluno ausente",
        ):
            initialize_answer_sheet(participation)

        self.assertFalse(
            AnswerSheet.objects.exists()
        )

    def test_cancelled_participation_is_rejected(self):
        participation = self.get_participation()
        participation.status = (
            Participation.Status.CANCELLED
        )
        participation.save()

        with self.assertRaisesMessage(
            ValidationError,
            "participação cancelada",
        ):
            initialize_answer_sheet(participation)

        self.assertFalse(
            AnswerSheet.objects.exists()
        )

    def test_answer_from_another_version_is_rejected(self):
        other_version = AssessmentVersion.objects.create(
            assessment=self.assessment,
            code="B",
            question_count=1,
            option_count=4,
            total_score=Decimal("10.00"),
        )

        other_question = Question.objects.create(
            version=other_version,
            component=self.component,
            number=1,
            correct_answer=Question.Answer.A,
        )

        answer_sheet = self.initialize()
        first_answer = answer_sheet.answers.order_by(
            "question__number"
        ).first()

        AnswerEntry.objects.filter(
            pk=first_answer.pk,
        ).update(
            question=other_question,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "não correspondem exatamente",
        ):
            process_answer_sheet(answer_sheet)

    def test_invalid_option_is_rejected(self):
        answer_sheet = self.initialize()
        answer = answer_sheet.answers.order_by(
            "question__number"
        ).first()

        answer.marking_status = (
            AnswerEntry.MarkingStatus.SINGLE
        )
        answer.selected_answer = Question.Answer.E

        with self.assertRaisesMessage(
            ValidationError,
            "A alternativa não existe nesta versão",
        ):
            answer.save()

    def test_transaction_rolls_back_on_breakdown_failure(self):
        answer_sheet = self.initialize()
        answer = answer_sheet.answers.order_by(
            "question__number"
        ).first()

        self.mark_single(
            answer,
            answer.question.correct_answer,
        )

        with patch(
            "applications.correction.save_breakdowns",
            side_effect=RuntimeError(
                "Falha simulada nos detalhamentos."
            ),
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "Falha simulada",
            ):
                process_answer_sheet(answer_sheet)

        answer_sheet.refresh_from_db()
        answer.refresh_from_db()

        self.assertEqual(
            answer_sheet.status,
            AnswerSheet.Status.DRAFT,
        )
        self.assertIsNone(answer.is_correct)
        self.assertEqual(
            answer.awarded_score,
            Decimal("0.00"),
        )
        self.assertEqual(
            AnswerSheetBreakdown.objects.count(),
            0,
        )

        participation = self.get_participation()

        self.assertEqual(
            participation.status,
            Participation.Status.EXPECTED,
        )

    def test_component_and_descriptor_breakdowns(self):
        answer_sheet = self.initialize()
        answers = self.get_answers(answer_sheet)

        self.mark_single(
            answers[0],
            answers[0].question.correct_answer,
        )
        self.mark_single(
            answers[2],
            answers[2].question.correct_answer,
        )

        answer_sheet = process_answer_sheet(
            answer_sheet
        )

        component = answer_sheet.breakdowns.get(
            dimension=(
                AnswerSheetBreakdown.Dimension.COMPONENT
            ),
            key="MAT",
        )

        self.assertEqual(component.question_count, 4)
        self.assertEqual(component.correct_count, 2)
        self.assertEqual(
            component.score,
            Decimal("6.00"),
        )
        self.assertEqual(
            component.maximum_score,
            Decimal("10.00"),
        )
        self.assertEqual(
            component.percentage,
            Decimal("60.00"),
        )

        technical_reasoning = (
            answer_sheet.breakdowns.get(
                dimension=(
                    AnswerSheetBreakdown.Dimension.DESCRIPTOR
                ),
                key="RT01",
            )
        )

        self.assertEqual(
            technical_reasoning.question_count,
            2,
        )
        self.assertEqual(
            technical_reasoning.correct_count,
            1,
        )
        self.assertEqual(
            technical_reasoning.score,
            Decimal("2.00"),
        )
        self.assertEqual(
            technical_reasoning.maximum_score,
            Decimal("4.00"),
        )
        self.assertEqual(
            technical_reasoning.percentage,
            Decimal("50.00"),
        )

        interpretation = answer_sheet.breakdowns.get(
            dimension=(
                AnswerSheetBreakdown.Dimension.DESCRIPTOR
            ),
            key="IN01",
        )

        self.assertEqual(
            interpretation.question_count,
            2,
        )
        self.assertEqual(
            interpretation.correct_count,
            1,
        )
        self.assertEqual(
            interpretation.score,
            Decimal("4.00"),
        )
        self.assertEqual(
            interpretation.maximum_score,
            Decimal("6.00"),
        )
        self.assertEqual(
            interpretation.percentage,
            Decimal("66.67"),
        )

    def test_reprocessing_does_not_duplicate_breakdowns(self):
        answer_sheet = process_answer_sheet(
            self.initialize()
        )

        first_breakdown_count = (
            answer_sheet.breakdowns.count()
        )

        answer = answer_sheet.answers.order_by(
            "question__number"
        ).first()

        self.mark_single(
            answer,
            answer.question.correct_answer,
        )

        answer_sheet = process_answer_sheet(
            answer_sheet
        )

        self.assertEqual(
            answer_sheet.breakdowns.count(),
            first_breakdown_count,
        )
        self.assertEqual(
            AnswerSheetBreakdown.objects.count(),
            3,
        )
        self.assertEqual(answer_sheet.correct_count, 1)

    def test_admin_initializes_selected_participation(self):
        model_admin = ParticipationAdmin(
            Participation,
            admin.site,
        )
        request = self.get_admin_request()

        queryset = Participation.objects.filter(
            pk=self.participation.pk,
        )

        with patch.object(
            model_admin,
            "message_user",
        ):
            model_admin.initialize_answer_sheets(
                request,
                queryset,
            )

        self.assertTrue(
            AnswerSheet.objects.filter(
                participation=self.participation,
            ).exists()
        )
        self.assertEqual(
            AnswerEntry.objects.filter(
                answer_sheet__participation=(
                    self.participation
                ),
            ).count(),
            4,
        )

    def test_admin_validates_selected_sheet(self):
        answer_sheet = self.initialize()

        model_admin = AnswerSheetAdmin(
            AnswerSheet,
            admin.site,
        )
        request = self.get_admin_request()

        with patch.object(
            model_admin,
            "message_user",
        ):
            model_admin.validate_selected(
                request,
                AnswerSheet.objects.filter(
                    pk=answer_sheet.pk,
                ),
            )

        answer_sheet.refresh_from_db()

        self.assertEqual(
            answer_sheet.status,
            AnswerSheet.Status.VALIDATED,
        )
        self.assertEqual(
            answer_sheet.validated_by,
            self.admin_user,
        )
        self.assertIsNotNone(
            answer_sheet.validated_at
        )

        participation = self.get_participation()

        self.assertEqual(
            participation.status,
            Participation.Status.ANSWER_SHEET_RECEIVED,
        )

    def test_admin_processes_selected_sheet(self):
        answer_sheet = self.initialize()

        model_admin = AnswerSheetAdmin(
            AnswerSheet,
            admin.site,
        )
        request = self.get_admin_request()

        with patch.object(
            model_admin,
            "message_user",
        ):
            model_admin.process_selected(
                request,
                AnswerSheet.objects.filter(
                    pk=answer_sheet.pk,
                ),
            )

        answer_sheet.refresh_from_db()

        self.assertEqual(
            answer_sheet.status,
            AnswerSheet.Status.PROCESSED,
        )
        self.assertEqual(
            answer_sheet.processed_by,
            self.admin_user,
        )
        self.assertEqual(answer_sheet.blank_count, 4)
        self.assertEqual(
            answer_sheet.breakdowns.count(),
            3,
        )

    def test_admin_reopens_processed_sheet(self):
        answer_sheet = process_answer_sheet(
            self.initialize()
        )

        model_admin = AnswerSheetAdmin(
            AnswerSheet,
            admin.site,
        )
        request = self.get_admin_request()

        with patch.object(
            model_admin,
            "message_user",
        ):
            model_admin.reopen_selected(
                request,
                AnswerSheet.objects.filter(
                    pk=answer_sheet.pk,
                ),
            )

        answer_sheet.refresh_from_db()

        self.assertEqual(
            answer_sheet.status,
            AnswerSheet.Status.DRAFT,
        )
        self.assertEqual(answer_sheet.correct_count, 0)
        self.assertEqual(answer_sheet.incorrect_count, 0)
        self.assertEqual(answer_sheet.blank_count, 0)
        self.assertEqual(answer_sheet.multiple_count, 0)
        self.assertEqual(
            answer_sheet.score,
            Decimal("0.00"),
        )
        self.assertEqual(
            answer_sheet.breakdowns.count(),
            0,
        )
        self.assertEqual(
            answer_sheet.answers.exclude(
                is_correct=None,
            ).count(),
            0,
        )

    def test_admin_save_without_changes_preserves_processed(self):
        answer_sheet = process_answer_sheet(
            self.initialize()
        )

        model_admin = AnswerSheetAdmin(
            AnswerSheet,
            admin.site,
        )
        request = self.get_admin_request()

        class UnchangedAnswerFormSet:
            model = AnswerEntry

            def has_changed(self):
                return False

            def save(self, commit=True):
                return []

            def save_m2m(self):
                return None

        form = SimpleNamespace(
            instance=answer_sheet,
        )
        formset = UnchangedAnswerFormSet()

        model_admin.save_formset(
            request=request,
            form=form,
            formset=formset,
            change=True,
        )

        answer_sheet.refresh_from_db()

        self.assertEqual(
            answer_sheet.status,
            AnswerSheet.Status.PROCESSED,
        )
        self.assertIsNotNone(
            answer_sheet.processed_at
        )

    def test_application_admin_has_no_duplicate_actions(self):
        model_admin = SimulationApplicationAdmin(
            SimulationApplication,
            admin.site,
        )

        actions = tuple(model_admin.actions)

        self.assertEqual(
            len(actions),
            len(set(actions)),
        )
        self.assertIn(
            "create_data_portal",
            actions,
        )
        self.assertIn(
            "generate_participations",
            actions,
        )
        self.assertIn(
            "mark_as_preparing",
            actions,
        )
        self.assertIn(
            "mark_as_ready",
            actions,
        )

