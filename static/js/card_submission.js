document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector(
        "#card-submission-form"
    );

    if (!form) {
        return;
    }

    const school = document.querySelector(
        "#id_school"
    );
    const classroom = document.querySelector(
        "#id_application_classroom"
    );
    const student = document.querySelector(
        "#id_participation"
    );
    const imageInput = document.querySelector(
        "#id_image"
    );
    const photoPicker = document.querySelector(
        "#photo-picker"
    );
    const preview = document.querySelector(
        "#photo-preview"
    );
    const selectedFile = document.querySelector(
        "#selected-file"
    );
    const submitButton = document.querySelector(
        "#submit-card-button"
    );

    const classroomUrl =
        form.dataset.classroomsUrl;
    const studentUrl =
        form.dataset.studentsUrl;

    function resetSelect(
        select,
        placeholder
    ) {
        select.innerHTML = "";

        const option = document.createElement(
            "option"
        );
        option.value = "";
        option.textContent = placeholder;

        select.appendChild(option);
    }

    function fillSelect(
        select,
        results,
        placeholder
    ) {
        resetSelect(
            select,
            placeholder
        );

        for (const result of results) {
            const option =
                document.createElement("option");

            option.value = result.id;
            option.textContent = result.label;

            if (result.registration) {
                option.textContent +=
                    ` — ${result.registration}`;
            }

            select.appendChild(option);
        }
    }

    async function loadClassrooms() {
        resetSelect(
            classroom,
            "Carregando turmas..."
        );
        resetSelect(
            student,
            "Selecione primeiro a turma"
        );

        classroom.disabled = true;
        student.disabled = true;

        if (!school.value) {
            resetSelect(
                classroom,
                "Selecione primeiro a escola"
            );
            classroom.disabled = false;
            return;
        }

        const url = new URL(
            classroomUrl,
            window.location.origin
        );
        url.searchParams.set(
            "school",
            school.value
        );

        try {
            const response = await fetch(url);

            if (!response.ok) {
                throw new Error(
                    "Não foi possível carregar."
                );
            }

            const data = await response.json();

            fillSelect(
                classroom,
                data.results,
                "Selecione a turma"
            );
        } catch (error) {
            resetSelect(
                classroom,
                "Erro ao carregar turmas"
            );
        } finally {
            classroom.disabled = false;
        }
    }

    async function loadStudents() {
        resetSelect(
            student,
            "Carregando alunos..."
        );
        student.disabled = true;

        if (!classroom.value) {
            resetSelect(
                student,
                "Selecione primeiro a turma"
            );
            return;
        }

        const url = new URL(
            studentUrl,
            window.location.origin
        );
        url.searchParams.set(
            "application_classroom",
            classroom.value
        );

        try {
            const response = await fetch(url);

            if (!response.ok) {
                throw new Error(
                    "Não foi possível carregar."
                );
            }

            const data = await response.json();

            fillSelect(
                student,
                data.results,
                "Selecione o aluno"
            );
        } catch (error) {
            resetSelect(
                student,
                "Erro ao carregar alunos"
            );
        } finally {
            student.disabled = false;
        }
    }

    school.addEventListener(
        "change",
        loadClassrooms
    );

    classroom.addEventListener(
        "change",
        loadStudents
    );

    imageInput.addEventListener(
        "change",
        () => {
            const file = imageInput.files[0];

            if (!file) {
                photoPicker.classList.remove(
                    "has-preview"
                );
                preview.removeAttribute("src");
                selectedFile.textContent = "";
                return;
            }

            const maximumSize =
                12 * 1024 * 1024;

            if (file.size > maximumSize) {
                window.alert(
                    "A imagem ultrapassa 12 MB."
                );
                imageInput.value = "";
                return;
            }

            if (!file.type.startsWith("image/")) {
                window.alert(
                    "Selecione uma imagem válida."
                );
                imageInput.value = "";
                return;
            }

            const imageUrl =
                URL.createObjectURL(file);

            preview.src = imageUrl;
            photoPicker.classList.add(
                "has-preview"
            );
            selectedFile.textContent =
                `${file.name} — ` +
                `${(
                    file.size / 1024 / 1024
                ).toFixed(2)} MB`;

            preview.onload = () => {
                URL.revokeObjectURL(
                    imageUrl
                );
            };
        }
    );

    form.addEventListener(
        "submit",
        () => {
            submitButton.disabled = true;
            submitButton.textContent =
                "Enviando cartão...";
        }
    );
});