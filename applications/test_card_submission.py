import base64
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)
from django.test import (
    TestCase,
    override_settings,
)
from django.urls import reverse
from django.utils import timezone

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
    AssessmentVersion,
)
from institutions.models import (
    Municipality,
    School,
)

from applications.models import (
    AnswerSheetImageSubmission,
    ApplicationClassroom,
    CardSubmissionPortal,
    Participation,
    SimulationApplication,
    validate_answer_sheet_image,
)

from django.contrib.auth import get_user_model


PNG_CONTENT = base64.b64decode(
    (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"
        "CAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
)


def uploaded_image(
    name="cartao.png",
):
    return SimpleUploadedFile(
        name,
        PNG_CONTENT,
        content_type="image/png",
    )


class CardSubmissionPortalTest(
    TestCase
):
    @classmethod
    def setUpClass(cls):
        cls.temporary_media = (
            tempfile.TemporaryDirectory()
        )
        cls.media_override = (
            override_settings(
                MEDIA_ROOT=(
                    cls.temporary_media.name
                )
            )
        )
        cls.media_override.enable()

        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        cls.media_override.disable()
        cls.temporary_media.cleanup()

    @classmethod
    def setUpTestData(cls):
        cls.municipality = (
            Municipality.objects.create(
                name="Município Portal Cartões",
                state="CE",
                ibge_code="2309999",
            )
        )
        
        cls.staff_user = (
            get_user_model()
            .objects
            .create_superuser(
                username="admin-cartoes",
                email="admin-cartoes@example.com",
                password="senha-teste-123",
            )
        )

        cls.school = School.objects.create(
            municipality=cls.municipality,
            name="Escola Portal Cartões",
            inep_code="23999991",
        )

        cls.academic_year = (
            AcademicYear.objects.create(
                year=2027,
                is_current=False,
            )
        )

        cls.stage = (
            EducationStage.objects.create(
                name="Etapa Portal Cartões",
                order=90,
            )
        )

        cls.grade = Grade.objects.create(
            stage=cls.stage,
            name="9º ano Portal",
            code="EF09-PORTAL",
            order=9,
        )

        cls.subject = Subject.objects.get(
            code="MAT",
        )

        cls.classroom = Classroom.objects.create(
            school=cls.school,
            academic_year=cls.academic_year,
            grade=cls.grade,
            name="A",
            shift=Classroom.Shift.MORNING,
        )
        cls.classroom.subjects.add(
            cls.subject
        )

        cls.student = Student.objects.create(
            school=cls.school,
            registration_code="PORTAL-001",
            full_name="Aluno Portal Teste",
        )

        cls.enrollment = (
            Enrollment.objects.create(
                student=cls.student,
                classroom=cls.classroom,
                status=Enrollment.Status.ACTIVE,
            )
        )

        cls.assessment = Assessment.objects.create(
            title="Avaliação Portal Cartões",
            code="AVALIACAO-PORTAL-2027",
            academic_year=cls.academic_year,
            subject=cls.subject,
            status=Assessment.Status.PUBLISHED,
        )
        cls.assessment.grades.add(
            cls.grade
        )

        cls.version = (
            AssessmentVersion.objects.create(
                assessment=cls.assessment,
                code="A",
                question_count=1,
                option_count=4,
                total_score=Decimal("10.00"),
            )
        )

        cls.application = (
            SimulationApplication.objects.create(
                title="Aplicação Portal Cartões",
                assessment=cls.assessment,
                municipality=cls.municipality,
                application_date=date(
                    2027,
                    9,
                    10,
                ),
                status=(
                    SimulationApplication
                    .Status
                    .READY
                ),
            )
        )

        cls.application_classroom = (
            ApplicationClassroom.objects.create(
                application=cls.application,
                classroom=cls.classroom,
            )
        )

        cls.participation = (
            Participation.objects.create(
                application=cls.application,
                application_classroom=(
                    cls.application_classroom
                ),
                student=cls.student,
                enrollment=cls.enrollment,
                assessment_version=cls.version,
            )
        )

        cls.portal = (
            CardSubmissionPortal.objects.create(
                application=cls.application,
                contact_name="Responsável Teste",
                contact_email=(
                    "responsavel@example.com"
                ),
            )
        )

    def detail_url(self):
        return reverse(
            "card_submission:detail",
            kwargs={
                "token": self.portal.token,
            },
        )

    def post_submission(
        self,
        image=None,
    ):
        return self.client.post(
            self.detail_url(),
            data={
                "school": self.school.pk,
                "application_classroom": (
                    self
                    .application_classroom
                    .pk
                ),
                "participation": (
                    self.participation.pk
                ),
                "sender_name": (
                    "Encarregado de Teste"
                ),
                "image": (
                    image
                    or uploaded_image()
                ),
            },
        )

    def test_active_portal_opens(self):
        response = self.client.get(
            self.detail_url()
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "Fotografe e envie",
        )

    def test_inactive_portal_is_rejected(self):
        self.portal.is_active = False
        self.portal.save(
            update_fields=["is_active"]
        )

        response = self.client.get(
            self.detail_url()
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_expired_portal_is_rejected(self):
        self.portal.expires_at = (
            timezone.now()
            - timedelta(minutes=1)
        )
        self.portal.save(
            update_fields=["expires_at"]
        )

        response = self.client.get(
            self.detail_url()
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_classroom_endpoint(self):
        url = reverse(
            "card_submission:classrooms",
            kwargs={
                "token": self.portal.token,
            },
        )

        response = self.client.get(
            url,
            {
                "school": self.school.pk,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.json()["results"][0]["id"],
            self.application_classroom.pk,
        )

    def test_student_endpoint(self):
        url = reverse(
            "card_submission:students",
            kwargs={
                "token": self.portal.token,
            },
        )

        response = self.client.get(
            url,
            {
                "application_classroom": (
                    self
                    .application_classroom
                    .pk
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.json()["results"][0]["id"],
            self.participation.pk,
        )
        self.assertEqual(
            response.json()["results"][0]["label"],
            self.student.full_name,
        )

    def test_successful_upload(self):
        response = self.post_submission()

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertEqual(
            AnswerSheetImageSubmission
            .objects
            .count(),
            1,
        )

        submission = (
            AnswerSheetImageSubmission
            .objects
            .get()
        )

        self.assertEqual(
            submission.portal,
            self.portal,
        )
        self.assertEqual(
            submission.participation,
            self.participation,
        )
        self.assertEqual(
            submission.sender_name,
            "Encarregado de Teste",
        )
        self.assertTrue(
            submission.protocol.startswith(
                "ENV-"
            )
        )

        file_path = Path(
            submission.image.path
        )

        self.assertTrue(
            file_path.exists()
        )

    def test_upload_marks_participation_received(
        self,
    ):
        self.post_submission()

        self.participation.refresh_from_db()

        self.assertEqual(
            self.participation.status,
            (
                Participation.Status
                .ANSWER_SHEET_RECEIVED
            ),
        )

    def test_processed_participation_is_preserved(
        self,
    ):
        self.participation.status = (
            Participation.Status.PROCESSED
        )
        self.participation.save(
            update_fields=["status"]
        )

        self.post_submission(
            uploaded_image(
                "processado.png"
            )
        )

        self.participation.refresh_from_db()

        self.assertEqual(
            self.participation.status,
            Participation.Status.PROCESSED,
        )

    def test_absent_participation_is_rejected(
        self,
    ):
        self.participation.status = (
            Participation.Status.ABSENT
        )
        self.participation.save(
            update_fields=["status"]
        )

        response = self.post_submission(
            uploaded_image(
                "ausente.png"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            AnswerSheetImageSubmission
            .objects
            .count(),
            0,
        )

    def test_invalid_extension_is_rejected(self):
        response = self.post_submission(
            uploaded_image(
                "cartao.txt"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            AnswerSheetImageSubmission
            .objects
            .count(),
            0,
        )
        self.assertContains(
            response,
            "JPG, PNG ou WEBP",
        )

    def test_oversized_file_is_rejected(self):
        file = SimpleNamespace(
            size=(
                12 * 1024 * 1024
                + 1
            )
        )

        with self.assertRaisesMessage(
            ValidationError,
            "não pode ultrapassar 12 MB",
        ):
            validate_answer_sheet_image(
                file
            )

    def test_success_page_uses_portal_token(
        self,
    ):
        self.post_submission()

        submission = (
            AnswerSheetImageSubmission
            .objects
            .get()
        )

        url = reverse(
            "card_submission:success",
            kwargs={
                "token": self.portal.token,
                "submission_code": (
                    submission.submission_code
                ),
            },
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            submission.protocol,
        )
        self.assertContains(
            response,
            self.student.full_name,
        )
        
    def test_image_requires_staff_login(self):
        self.post_submission()

        submission = (
            AnswerSheetImageSubmission
            .objects
            .get()
        )

        url = reverse(
            "card_submission:secure_image",
            kwargs={
                "submission_code": (
                    submission.submission_code
                ),
            },
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertIn(
            "/admin/login/",
            response["Location"],
        )

    def test_staff_can_view_image(self):
        self.post_submission()

        submission = (
            AnswerSheetImageSubmission
            .objects
            .get()
        )

        self.client.force_login(
            self.staff_user
        )

        url = reverse(
            "card_submission:secure_image",
            kwargs={
                "submission_code": (
                    submission.submission_code
                ),
            },
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response["Cache-Control"],
            "private, no-store",
        )
        self.assertEqual(
            response[
                "X-Content-Type-Options"
            ],
            "nosniff",
        )