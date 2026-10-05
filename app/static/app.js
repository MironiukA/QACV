const form = document.querySelector("#analysis-form");
const sourceOptions = document.querySelectorAll(".source-option");
const urlSource = document.querySelector("#url-source");
const textSource = document.querySelector("#text-source");
const resumeInput = document.querySelector("#resume");
const resumeLabel = document.querySelector("#resume-label");
const submitButton = document.querySelector("#submit-button");
const formMessage = document.querySelector("#form-message");
const progress = document.querySelector("#progress");
const progressText = document.querySelector("#progress-text");
const results = document.querySelector("#results");
const answersForm = document.querySelector("#answers-form");
const answersMessage = document.querySelector("#answers-message");
const generateResumeButton = document.querySelector("#generate-resume-button");
const saveResumeButton = document.querySelector("#save-resume-button");
const exportPdfButton = document.querySelector("#export-pdf-button");
const resumeEditMessage = document.querySelector("#resume-edit-message");
const startScreeningButton = document.querySelector("#start-screening-button");
const screeningForm = document.querySelector("#screening-form");
const screeningAnswer = document.querySelector("#screening-answer");
const screeningMessage = document.querySelector("#screening-message");
const startTechnicalButton = document.querySelector("#start-technical-button");
const openInterviewChatButton = document.querySelector("#open-interview-chat");

let currentApplicationId = null;
let currentResumeVersionId = null;
let currentScreeningSessionId = null;

loadPrivacyNotice();

let source = "url";

sourceOptions.forEach((button) => {
  button.addEventListener("click", () => {
    source = button.dataset.source;
    sourceOptions.forEach((option) => option.classList.toggle("is-active", option === button));
    urlSource.hidden = source !== "url";
    textSource.hidden = source !== "text";
  });
});

resumeInput.addEventListener("change", () => {
  resumeLabel.textContent = resumeInput.files[0]?.name || "Добавить резюме";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formMessage.textContent = "";
  results.hidden = true;

  const name = document.querySelector("#name").value.trim();
  const email = document.querySelector("#email").value.trim();
  const phone = document.querySelector("#phone").value.trim();
  const file = resumeInput.files[0];
  const url = document.querySelector("#vacancy-url").value.trim();
  const title = document.querySelector("#vacancy-title").value.trim();
  const description = document.querySelector("#vacancy-text").value.trim();

  if (!name || !email || (source === "url" && !url) || (source === "text" && (!title || !description))) {
    formMessage.textContent = "Заполните имя, email и источник вакансии.";
    return;
  }

  setLoading(true, "Создаем локальный профиль...");
  try {
    const profile = await request("/profiles", "POST", { name, email, phone: phone || null });

    if (file) {
      setProgress("Извлекаем текст резюме...");
      const upload = new FormData();
      upload.append("file", file);
      await request(`/profiles/${profile.id}/resume`, "POST", upload, true);
    }

    setProgress(source === "url" ? "Загружаем публичную вакансию и запускаем локальный AI..." : "Сохраняем вакансию...");
    let intake;
    if (source === "url") {
      intake = await request("/vacancies/from-url", "POST", { source_url: url });
    } else {
      const vacancy = await request("/vacancies", "POST", { title, description });
      const requirements = await request(`/vacancies/${vacancy.id}/requirements/extract`, "POST");
      const analysis = await request(`/vacancies/${vacancy.id}/requirements/ai-analysis`, "POST");
      intake = {
        vacancy,
        requirements: analysis.verified_requirements.length ? analysis.verified_requirements : requirements,
        ai_analysis: analysis.analysis,
        ai_analysis_error: null,
        rejected_ai_requirements: analysis.rejected_requirements,
      };
    }

    setProgress(file ? "Сверяем требования с резюме..." : "Подготавливаем скрининг...");
    const application = await request("/applications", "POST", { profile_id: profile.id, vacancy_id: intake.vacancy.id });
    currentApplicationId = application.id;
    const matching = file ? await request(`/applications/${application.id}/match`, "POST", {}) : null;
    renderResults(intake, matching);
  } catch (error) {
    formMessage.textContent = error.message || "Не удалось обработать данные.";
  } finally {
    setLoading(false);
  }
});

async function request(path, method, body, isForm = false) {
  const options = { method, headers: {} };
  if (isForm) {
    options.body = body;
  } else {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Сервер вернул ошибку.");
  }
  return data;
}

function setLoading(isLoading, text = "") {
  submitButton.disabled = isLoading;
  submitButton.querySelector("span").textContent = isLoading ? "Анализируем..." : "Разобрать вакансию";
  progress.hidden = !isLoading;
  if (isLoading) setProgress(text);
}

function setProgress(text) {
  progressText.textContent = text;
}

function renderResults(data, matching) {
  document.querySelector("#result-title").textContent = data.vacancy.title;
  document.querySelector("#result-id").textContent = `VACANCY #${data.vacancy.id}`;
  const requirements = document.querySelector("#requirements");
  requirements.replaceChildren();
  data.requirements.forEach((item) => {
    const card = document.createElement("div");
    card.className = "requirement";
    const priority = document.createElement("i");
    priority.className = `priority ${item.priority === "nice_to_have" ? "nice" : ""}`;
    priority.textContent = item.priority === "must_have" ? "ОБЯЗАТЕЛЬНО" : "ЖЕЛАТЕЛЬНО";
    const name = document.createElement("strong");
    name.textContent = item.name;
    const evidence = document.createElement("span");
    evidence.textContent = item.source_text ? `«${item.source_text}»` : "Источник не указан";
    card.append(priority, name, evidence);
    requirements.append(card);
  });
  if (!data.requirements.length) requirements.textContent = "Явные требования не найдены.";

  document.querySelector("#ai-analysis").textContent = data.ai_analysis || "AI-анализ пока недоступен.";
  const warning = document.querySelector("#analysis-warning");
  const messages = [];
  if (data.ai_analysis_error) messages.push(data.ai_analysis_error);
  if (data.rejected_ai_requirements) messages.push(`Отклонено неподтвержденных пунктов: ${data.rejected_ai_requirements}.`);
  warning.hidden = !messages.length;
  warning.textContent = messages.join(" ");
  if (matching) {
    renderMatching(matching);
  } else {
    document.querySelector("#matching-result").hidden = true;
    document.querySelector("#generated-resume").hidden = true;
    document.querySelector("#screening").hidden = false;
  }
  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderMatching(matching) {
  currentApplicationId = matching.application_id;
  const matchingResult = document.querySelector("#matching-result");
  const matches = document.querySelector("#matches");
  const questions = document.querySelector("#questions");
  matches.replaceChildren();
  questions.replaceChildren();

  matching.matches.forEach((item) => {
    const card = document.createElement("div");
    card.className = `match ${item.status === "confirmed" ? "is-confirmed" : "is-question"}`;
    const name = document.createElement("strong");
    name.textContent = item.requirement_name;
    const detail = document.createElement("span");
    detail.textContent = item.status === "confirmed" ? `Подтверждено: «${item.evidence}»` : "Не подтверждено в резюме";
    card.append(name, detail);
    matches.append(card);
  });

  matching.clarification_questions.forEach((item) => {
    const question = document.createElement("label");
    question.className = "question";
    const questionText = document.createElement("span");
    questionText.textContent = item.question;
    const answer = document.createElement("textarea");
    answer.rows = 3;
    answer.placeholder = "Опишите проект, задачи, период и уровень самостоятельности...";
    answer.dataset.questionId = item.id;
    const include = document.createElement("label");
    include.className = "include-option";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.dataset.includeQuestionId = item.id;
    const includeText = document.createElement("span");
    includeText.textContent = "Добавить подтвержденный опыт в новое резюме";
    include.append(checkbox, includeText);
    question.append(questionText, answer, include);
    questions.append(question);
  });
  if (!matching.clarification_questions.length) questions.textContent = "Дополнительные вопросы не нужны.";
  matchingResult.hidden = false;
  document.querySelector("#screening").hidden = false;
}

answersForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentApplicationId) return;

  answersMessage.textContent = "";
  const answers = [...document.querySelectorAll("textarea[data-question-id]")]
    .filter((field) => field.value.trim())
    .map((field) => ({
      question_id: Number(field.dataset.questionId),
      answer: field.value.trim(),
      include_in_resume: document.querySelector(`input[data-include-question-id="${field.dataset.questionId}"]`).checked,
    }));
  const additionalNote = document.querySelector("#additional-note").value.trim();
  const includeAdditionalNote = document.querySelector("#include-additional-note").checked;

  generateResumeButton.disabled = true;
  generateResumeButton.textContent = "Создаем локальную версию...";
  try {
    const saved = await request(`/applications/${currentApplicationId}/clarification-answers`, "POST", {
      answers,
      additional_note: additionalNote || null,
      include_additional_note: includeAdditionalNote,
    });
    renderRefinedFacts(saved.processed_answers);
    const version = await request(`/applications/${currentApplicationId}/resume/generate`, "POST", {});
    currentResumeVersionId = version.id;
    document.querySelector("#resume-version-id").textContent = `VERSION #${version.id}`;
    document.querySelector("#resume-content").value = version.content;
    resumeEditMessage.textContent = "Можно отредактировать текст перед сохранением или экспортом.";
    document.querySelector("#generated-resume").hidden = false;
    document.querySelector("#generated-resume").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    answersMessage.textContent = error.message || "Не удалось создать резюме.";
  } finally {
    generateResumeButton.disabled = false;
    generateResumeButton.textContent = "Сохранить ответы и создать резюме";
  }
});

function renderRefinedFacts(processedAnswers) {
  const refinedFacts = document.querySelector("#refined-facts");
  refinedFacts.replaceChildren();
  processedAnswers.forEach((item) => {
    const fact = document.createElement("div");
    fact.className = `refined-fact ${item.include_in_resume ? "" : "is-excluded"}`;
    const section = document.createElement("b");
    section.textContent = `${sectionLabel(item.resume_section)}${item.include_in_resume ? "" : " / не включено"}`;
    const content = document.createElement("span");
    content.textContent = item.refined_answer;
    fact.append(section, content);
    refinedFacts.append(fact);
  });
  refinedFacts.hidden = !processedAnswers.length;
}

function sectionLabel(section) {
  return {
    skills: "Навыки",
    experience: "Опыт",
    projects: "Проекты",
    summary: "Профиль",
  }[section] || "Опыт";
}

async function loadPrivacyNotice() {
  const privacyText = document.querySelector("#privacy-text");
  try {
    const privacy = await fetch("/privacy").then((response) => response.json());
    privacyText.textContent = privacy.ai_data_leaves_device
      ? "AI-режим OpenAI: текст резюме, вакансии и ответов передается в облачную модель."
      : "Резюме и AI-анализ локальны. Внешняя сеть нужна только для загрузки публичной ссылки на вакансию.";
  } catch {
    privacyText.textContent = "Не удалось определить режим обработки данных.";
  }
}

startScreeningButton.addEventListener("click", async () => {
  if (!currentApplicationId) return;
  startScreeningButton.disabled = true;
  try {
    const step = await request(`/applications/${currentApplicationId}/screening/start`, "POST", {});
    renderScreeningStep(step);
  } catch (error) {
    screeningMessage.textContent = error.message || "Не удалось начать скрининг.";
  } finally {
    startScreeningButton.disabled = false;
  }
});

openInterviewChatButton.addEventListener("click", () => {
  if (currentApplicationId) window.location.assign(`/interview/${currentApplicationId}`);
});

screeningForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentScreeningSessionId || !screeningAnswer.value.trim()) {
    screeningMessage.textContent = "Напишите ответ перед отправкой.";
    return;
  }
  const button = document.querySelector("#send-screening-answer");
  button.disabled = true;
  screeningMessage.textContent = "Локальный AI оценивает ответ...";
  try {
    const step = await request(`/interviews/${currentScreeningSessionId}/answers`, "POST", {
      answer: screeningAnswer.value.trim(),
    });
    screeningAnswer.value = "";
    renderScreeningStep(step);
  } catch (error) {
    screeningMessage.textContent = error.message || "Не удалось оценить ответ.";
  } finally {
    button.disabled = false;
  }
});

startTechnicalButton.addEventListener("click", async () => {
  if (!currentApplicationId) return;
  try {
    const step = await request(`/applications/${currentApplicationId}/technical/start`, "POST", {});
    renderScreeningStep(step);
  } catch (error) {
    screeningMessage.textContent = error.message || "Не удалось начать технический этап.";
  }
});

function renderScreeningStep(step) {
  currentScreeningSessionId = step.session_id;
  const result = document.querySelector("#screening-result");
  if (!step.completed) {
    document.querySelector("#screening-topic").textContent = `Вопрос по вакансии / ${step.stage}`;
    document.querySelector("#screening-question").textContent = step.question;
    screeningMessage.textContent = "";
    screeningForm.hidden = false;
    result.hidden = true;
    startScreeningButton.hidden = true;
    return;
  }

  screeningForm.hidden = true;
  result.hidden = false;
  document.querySelector("#screening-status").textContent = step.stage === "technical"
    ? "Техническое собеседование завершено"
    : step.passed ? "Скрининг пройден" : "Скрининг требует подготовки";
  const recommendations = document.querySelector("#screening-recommendations");
  recommendations.replaceChildren();
  step.recommendations.forEach((item) => {
    const recommendation = document.createElement("div");
    recommendation.className = "recommendation";
    recommendation.textContent = item;
    recommendations.append(recommendation);
  });
  startTechnicalButton.hidden = !step.passed;
}

saveResumeButton.addEventListener("click", saveResumeVersion);

exportPdfButton.addEventListener("click", async () => {
  if (!currentResumeVersionId) return;
  try {
    await saveResumeVersion();
    window.location.assign(`/resume-versions/${currentResumeVersionId}/export.pdf`);
  } catch {
    // The save function displays the server error next to the buttons.
  }
});

async function saveResumeVersion() {
  if (!currentResumeVersionId) return;
  const content = document.querySelector("#resume-content").value.trim();
  if (!content) {
    resumeEditMessage.textContent = "Резюме не может быть пустым.";
    throw new Error("Resume is empty");
  }
  saveResumeButton.disabled = true;
  exportPdfButton.disabled = true;
  try {
    const version = await request(`/resume-versions/${currentResumeVersionId}`, "PATCH", { content });
    document.querySelector("#resume-content").value = version.content;
    resumeEditMessage.textContent = "Правки сохранены локально.";
    return version;
  } catch (error) {
    resumeEditMessage.textContent = error.message || "Не удалось сохранить правки.";
    throw error;
  } finally {
    saveResumeButton.disabled = false;
    exportPdfButton.disabled = false;
  }
}
