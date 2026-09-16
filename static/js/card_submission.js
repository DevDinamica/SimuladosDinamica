document.addEventListener(
    "DOMContentLoaded",
    () => {
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
        const senderName = document.querySelector(
            "#id_sender_name"
        );
        const uploadList = document.querySelector(
            "#discipline-upload-list"
        );
        const generalError = document.querySelector(
            "#submission-general-error"
        );
        const submitButton = document.querySelector(
            "#submit-card-button"
        );

        const classroomUrl =
            form.dataset.classroomsUrl;
        const studentUrl =
            form.dataset.studentsUrl;
        const cardUrl =
            form.dataset.cardsUrl;

        const csrfInput = form.querySelector(
            "[name='csrfmiddlewaretoken']"
        );

        function resetSelect(
            select,
            placeholder
        ) {
            select.innerHTML = "";

            const option =
                document.createElement("option");

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
                    document.createElement(
                        "option"
                    );

                option.value = result.id;
                option.textContent =
                    result.label;

                if (result.registration) {
                    option.textContent +=
                        ` — ${result.registration}`;
                }

                select.appendChild(option);
            }
        }

        function showEmptyCards(message) {
            uploadList.innerHTML = "";

            const empty =
                document.createElement("div");

            empty.className =
                "discipline-empty-state";
            empty.textContent = message;

            uploadList.appendChild(empty);
        }

        function updateSubmitAvailability() {
            const availableInputs = (
                uploadList.querySelectorAll(
                    (
                        ".discipline-upload-card "
                        + "input[type='file']"
                        + ":not(:disabled)"
                    )
                )
            );

            if (!availableInputs.length) {
                submitButton.disabled = true;
                submitButton.textContent = (
                    "Todos os cartões já foram enviados"
                );
                return;
            }

            submitButton.disabled = false;
            submitButton.textContent = (
                "Enviar cartões selecionados"
            );
        }

        function formatFileSize(size) {
            return (
                `${(
                    size / 1024 / 1024
                ).toFixed(2)} MB`
            );
        }

        function validateFile(file) {
            if (!file) {
                return "";
            }

            const maximumSize =
                12 * 1024 * 1024;

            if (file.size > maximumSize) {
                return (
                    "A imagem ultrapassa 12 MB."
                );
            }

            const allowedTypes = new Set([
                "image/jpeg",
                "image/png",
                "image/webp",
            ]);

            if (
                file.type
                && !allowedTypes.has(file.type)
            ) {
                return (
                    "Selecione uma imagem JPG, "
                    + "PNG ou WEBP."
                );
            }

            return "";
        }

        function createCardBlock(card) {
            const block =
                document.createElement(
                    "article"
                );

            block.className =
                "discipline-upload-card";
            block.dataset.cardId = card.id;

            const header =
                document.createElement("header");

            header.className =
                "discipline-upload-header";

            const titleGroup =
                document.createElement("div");

            const title =
                document.createElement("h3");

            title.textContent = card.label;

            const details =
                document.createElement("p");

            details.textContent =
                `Versão ${card.version} — `
                + `Código ${card.code}`;

            titleGroup.append(
                title,
                details
            );

            const badge =
                document.createElement("span");

            badge.className =
                "discipline-status";

            if (card.already_received) {
                badge.classList.add(
                    "received"
                );
                badge.textContent =
                    "✓ Já recebido";
            } else {
                badge.textContent =
                    "Aguardando foto";
            }

            header.append(
                titleGroup,
                badge
            );

            block.appendChild(header);

            if (card.already_received) {
                const received =
                    document.createElement("div");

                received.className =
                    "discipline-received-box";

                const text =
                    document.createElement("span");

                text.textContent =
                    "Este cartão já foi enviado.";

                received.appendChild(text);

                if (card.protocol) {
                    const protocol =
                        document.createElement(
                            "strong"
                        );

                    protocol.textContent =
                        card.protocol;

                    received.appendChild(
                        protocol
                    );
                }

                block.appendChild(received);

                return block;
            }

            const picker =
                document.createElement("label");

            picker.className =
                "discipline-photo-picker";

            const input =
                document.createElement("input");

            input.type = "file";
            input.accept = (
                "image/jpeg,"
                + "image/png,"
                + "image/webp"
            );
            input.setAttribute(
                "capture",
                "environment"
            );
            input.dataset.cardId = card.id;

            const placeholder =
                document.createElement("span");

            placeholder.className =
                "discipline-photo-placeholder";

            placeholder.innerHTML = `
                <span class="camera-icon">📷</span>
                <strong>
                    Abrir câmera ou escolher imagem
                </strong>
                <small>
                    Fotografe o cartão inteiro,
                    sem cortar os marcadores.
                </small>
            `;

            const preview =
                document.createElement("img");

            preview.className =
                "discipline-photo-preview";
            preview.alt =
                `Prévia do cartão de ${card.label}`;

            picker.append(
                input,
                placeholder,
                preview
            );

            const selectedFile =
                document.createElement("p");

            selectedFile.className =
                "selected-file";

            const result =
                document.createElement("div");

            result.className =
                "discipline-result";
            result.setAttribute(
                "role",
                "status"
            );

            input.addEventListener(
                "change",
                () => {
                    result.textContent = "";
                    result.className =
                        "discipline-result";

                    const file =
                        input.files[0];

                    if (!file) {
                        picker.classList.remove(
                            "has-preview"
                        );
                        preview.removeAttribute(
                            "src"
                        );
                        selectedFile.textContent =
                            "";
                        return;
                    }

                    const error =
                        validateFile(file);

                    if (error) {
                        input.value = "";
                        result.textContent =
                            error;
                        result.classList.add(
                            "error"
                        );
                        return;
                    }

                    const imageUrl =
                        URL.createObjectURL(
                            file
                        );

                    preview.src = imageUrl;
                    picker.classList.add(
                        "has-preview"
                    );
                    selectedFile.textContent =
                        `${file.name} — `
                        + formatFileSize(
                            file.size
                        );

                    preview.onload = () => {
                        URL.revokeObjectURL(
                            imageUrl
                        );
                    };
                }
            );

            block.append(
                picker,
                selectedFile,
                result
            );

            return block;
        }

        function renderCards(cards) {
            uploadList.innerHTML = "";

            if (!cards.length) {
                showEmptyCards(
                    "Nenhum cartão disponível "
                    + "para este aluno."
                );

                updateSubmitAvailability();
                return;
            }

            for (const card of cards) {
                uploadList.appendChild(
                    createCardBlock(card)
                );
            }

            updateSubmitAvailability();
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
            showEmptyCards(
                "Selecione primeiro o aluno."
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
                const response =
                    await fetch(url);

                if (!response.ok) {
                    throw new Error();
                }

                const data =
                    await response.json();

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
            showEmptyCards(
                "Selecione primeiro o aluno."
            );
            student.disabled = true;

            if (!classroom.value) {
                resetSelect(
                    student,
                    "Selecione primeiro a turma"
                );
                student.disabled = false;
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
                const response =
                    await fetch(url);

                if (!response.ok) {
                    throw new Error();
                }

                const data =
                    await response.json();

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

        async function loadCards() {
            generalError.textContent = "";
            generalError.classList.remove(
                "success"
            );

            if (!student.value) {
                showEmptyCards(
                    "Selecione primeiro o aluno."
                );
                return;
            }

            showEmptyCards(
                "Carregando cartões..."
            );

            const url = new URL(
                cardUrl,
                window.location.origin
            );

            url.searchParams.set(
                "participation",
                student.value
            );

            try {
                const response =
                    await fetch(url);

                if (!response.ok) {
                    throw new Error();
                }

                const data =
                    await response.json();

                renderCards(
                    data.results
                );
            } catch (error) {
                showEmptyCards(
                    "Não foi possível carregar "
                    + "os cartões."
                );
            }
        }

        async function submitCard(
            block,
            input
        ) {
            const result =
                block.querySelector(
                    ".discipline-result"
                );

            const file = input.files[0];

            const data = new FormData();

            data.append(
                "csrfmiddlewaretoken",
                csrfInput.value
            );
            data.append(
                "school",
                school.value
            );
            data.append(
                "application_classroom",
                classroom.value
            );
            data.append(
                "participation",
                student.value
            );
            data.append(
                "participation_card",
                block.dataset.cardId
            );
            data.append(
                "sender_name",
                senderName.value
            );
            data.append(
                "image",
                file,
                file.name
            );

            result.className =
                "discipline-result loading";
            result.textContent =
                "Enviando fotografia...";

            try {
                const response = await fetch(
                    form.action
                    || window.location.href,
                    {
                        method: "POST",
                        body: data,
                        headers: {
                            "X-Requested-With":
                                "XMLHttpRequest",
                        },
                    }
                );

                const payload =
                    await response.json();

                if (!response.ok) {
                    const messages = (
                        Object.values(
                            payload.errors || {}
                        ).flat()
                    );

                    throw new Error(
                        messages.join(" ")
                        || "Não foi possível enviar."
                    );
                }

                result.className =
                    "discipline-result success";
                result.textContent =
                    `✓ Enviado — `
                    + payload.protocol;

                input.disabled = true;

                block.classList.add(
                    "submitted"
                );

                const badge =
                    block.querySelector(
                        ".discipline-status"
                    );

                badge.classList.add(
                    "received"
                );
                badge.textContent =
                    "✓ Recebido";

                return {
                    success: true,
                    payload,
                };
            } catch (error) {
                result.className =
                    "discipline-result error";
                result.textContent =
                    error.message;

                return {
                    success: false,
                    error,
                };
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

        student.addEventListener(
            "change",
            loadCards
        );

        form.addEventListener(
            "submit",
            async (event) => {
                event.preventDefault();

                generalError.textContent = "";

                generalError.classList.remove(
                    "success"
                );

                if (
                    !school.value
                    || !classroom.value
                    || !student.value
                ) {
                    generalError.textContent = (
                        "Selecione escola, turma "
                        + "e aluno."
                    );
                    return;
                }

                const selected = Array.from(
                    uploadList.querySelectorAll(
                        (
                            ".discipline-upload-card "
                            + "input[type='file']"
                        )
                    )
                ).filter(
                    input => (
                        input.files.length
                        && !input.disabled
                    )
                );

                if (!selected.length) {
                    generalError.textContent = (
                        "Selecione pelo menos uma "
                        + "fotografia."
                    );
                    return;
                }

                submitButton.disabled = true;
                submitButton.textContent =
                    selected.length === 1
                        ? "Enviando cartão..."
                        : "Enviando cartões...";

                const results = [];

                for (const input of selected) {
                    const block = input.closest(
                        ".discipline-upload-card"
                    );

                    results.push(
                        await submitCard(
                            block,
                            input
                        )
                    );
                }

                const successful =
                    results.filter(
                        item => item.success
                    ).length;

                const failed =
                    results.length
                    - successful;

                if (failed && successful) {
                    generalError.textContent = (
                        `${successful} cartão enviado. `
                        + `${failed} cartão não foi `
                        + "enviado. Corrija somente "
                        + "o item indicado e tente "
                        + "novamente."
                    );
                } else if (failed) {
                    generalError.textContent = (
                        "Nenhum cartão foi enviado. "
                        + "Confira os erros indicados."
                    );
                } else {
                    generalError.textContent = (
                        successful === 1
                            ? "Cartão enviado com sucesso."
                            : (
                                "Os dois cartões foram "
                                + "enviados com sucesso."
                            )
                    );

                    generalError.classList.add(
                        "success"
                    );
                }

                updateSubmitAvailability();
            }
        );
    }
);