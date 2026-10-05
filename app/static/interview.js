const applicationId = Number(window.location.pathname.split("/").pop());
const startButton = document.querySelector("#start-chat");
const chat = document.querySelector("#chat");
const empty = document.querySelector("#chat-empty");
const messages = document.querySelector("#messages");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#chat-input");
const status = document.querySelector("#chat-status");
const recordButton = document.querySelector("#record-audio");
const thinkingLoader = document.querySelector("#thinking-loader");
let sessionId = null;
let recorder = null;
let audioChunks = [];

startButton.addEventListener("click", async () => {
  startButton.disabled = true;
  setThinking(true);
  try {
    const turn = await request(`/applications/${applicationId}/interview-chat/start`, "POST", {
      mode: document.querySelector("#interview-mode").value,
    });
    sessionId = turn.session_id;
    addMessage("interviewer", turn.message);
    empty.hidden = true;
    chat.hidden = false;
  } catch (error) {
    status.textContent = error.message || "Не удалось начать интервью.";
  } finally { startButton.disabled = false; setThinking(false); }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = input.value.trim();
  if (!content || !sessionId) return;
  addMessage("candidate", content);
  input.value = "";
  status.textContent = "";
  setThinking(true);
  try {
    const turn = await request(`/interview-chat/${sessionId}/messages`, "POST", { content });
    addMessage("interviewer", turn.message);
  } catch (error) { status.textContent = error.message || "Не удалось получить следующий вопрос."; return; }
  finally { setThinking(false); }
  status.textContent = "";
});

document.querySelector("#complete-chat").addEventListener("click", async () => {
  if (!sessionId) return;
  status.textContent = ""; setThinking(true);
  try {
    const result = await request(`/interview-chat/${sessionId}/complete`, "POST", {});
    document.querySelector("#report-content").textContent = result.report;
    document.querySelector("#report").hidden = false;
    form.hidden = true;
    document.querySelector("#complete-chat").hidden = true;
  } catch (error) { status.textContent = error.message || "Не удалось сформировать отчет."; }
  finally { setThinking(false); }
});

recordButton.addEventListener("click", async () => {
  if (!sessionId) return;
  if (recorder?.state === "recording") { recorder.stop(); return; }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    status.textContent = "Браузер не поддерживает запись аудио.";
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    recorder = new MediaRecorder(stream);
    recorder.addEventListener("dataavailable", (event) => { if (event.data.size) audioChunks.push(event.data); });
    recorder.addEventListener("stop", async () => {
      stream.getTracks().forEach((track) => track.stop());
      recordButton.classList.remove("is-recording");
      recordButton.textContent = "Записать голос";
      const audio = new Blob(audioChunks, { type: recorder.mimeType || "audio/webm" });
      if (!audio.size) return;
      status.textContent = "Распознаем речь...";
      try {
        const formData = new FormData();
        formData.append("file", audio, "answer.webm");
        const response = await fetch(`/interview-chat/${sessionId}/transcribe`, { method: "POST", body: formData });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Не удалось распознать аудио.");
        input.value = input.value ? `${input.value}\n${data.text}` : data.text;
        status.textContent = "Текст распознан. При необходимости отредактируйте его перед отправкой.";
      } catch (error) { status.textContent = error.message || "Не удалось распознать аудио."; }
    });
    recorder.start();
    recordButton.classList.add("is-recording");
    recordButton.textContent = "Остановить запись";
    status.textContent = "Идет запись...";
  } catch { status.textContent = "Нужен доступ к микрофону."; }
});

function addMessage(role, content) {
  const item = document.createElement("article"); item.className = `message ${role}`;
  const label = document.createElement("small"); label.textContent = role === "interviewer" ? "AI INTERVIEWER" : "ВЫ";
  const text = document.createElement("div"); text.textContent = content;
  item.append(label, text); messages.append(item); item.scrollIntoView({ behavior:"smooth", block:"end" });
}

async function request(path, method, body) {
  const response = await fetch(path, { method, headers:{"Content-Type":"application/json"}, body:JSON.stringify(body) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Сервер вернул ошибку.");
  return data;
}

function setThinking(isThinking) { thinkingLoader.hidden = !isThinking; }
