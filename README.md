# QACV

Локальное веб-приложение для подготовки QA-кандидата к конкретной вакансии.

QACV принимает ссылку или текст вакансии, выделяет требования, сопоставляет их с резюме, задает уточняющие вопросы, создает адаптированную версию CV и проводит симуляцию скрининга или технического интервью в чате.

## Возможности

- Загрузка вакансии по публичной ссылке или ручная вставка текста.
- Сохранение вакансий, требований, профилей, резюме, заявок и истории интервью в PostgreSQL.
- Загрузка резюме в `PDF` и `DOCX` с извлечением текста.
- Анализ вакансии и структурированный профиль роли:
  - роль и предполагаемый уровень;
  - специализация QA;
  - must-have и nice-to-have требования;
  - управленческие требования;
  - high-risk gaps;
  - домен вакансии.
- Сопоставление требований вакансии с резюме.
- Уточняющие вопросы только по неподтвержденным требованиям.
- Редактирование пользовательских ответов AI-моделью без добавления новых фактов.
- Формирование новой версии резюме и экспорт в PDF.
- Быстрый скрининг по ключевым требованиям.
- Отдельная страница живого интервью с режимами:
  - `HR_SCREEN`;
  - `TECH_SCREEN`;
  - `FULL_SCREEN`;
  - `HARD_MODE`.
- Итоговый отчет по интервью: сильные стороны, пробелы, рекомендации, вероятные темы и план подготовки.
- Голосовой ответ в чате с распознаванием речи через OpenAI Transcription.

## Технологии

- Python 3.13+
- FastAPI
- PostgreSQL 17
- SQLAlchemy 2
- Alembic
- OpenAI API
- Ollama как альтернативный локальный AI-провайдер
- HTML, CSS и JavaScript без отдельного frontend-сервера
- ReportLab для PDF-экспорта

## Быстрый Запуск

### 1. Клонировать репозиторий

```bash
git clone <REPOSITORY_URL>
cd QACV
```

### 2. Создать виртуальное окружение

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Запустить PostgreSQL

Проект рассчитан на PostgreSQL в Docker. Пример запуска:

```bash
docker run --name qacv-postgres \
  -e POSTGRES_DB=qacv \
  -e POSTGRES_USER=qacv \
  -e POSTGRES_PASSWORD=qacv_password \
  -p 5432:5432 \
  -d postgres:17
```

Если контейнер уже создан, но остановлен:

```bash
docker start qacv-postgres
```

Проверка подключения:

```bash
PGPASSWORD='qacv_password' psql -h localhost -p 5432 -U qacv -d qacv -c 'SELECT current_database();'
```

### 5. Создать `.env`

Создай файл `.env` в корне проекта. Он игнорируется Git и не должен попадать в репозиторий.

```env
DATABASE_URL=postgresql+psycopg://qacv:qacv_password@localhost:5432/qacv

# Разрешает загрузку текста публичной вакансии по URL.
REMOTE_VACANCY_FETCH_ENABLED=true

# Основной AI-провайдер для интервью и анализа.
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1
OPENAI_WEB_RESEARCH_ENABLED=true
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe

# Локальный fallback. Используется только при AI_PROVIDER=ollama.
LOCAL_LLM_URL=http://127.0.0.1:11434
LOCAL_LLM_MODEL=qwen2.5:7b
```

Не публикуй `OPENAI_API_KEY` в GitHub, чатах, скриншотах или исходном коде.

### 6. Применить миграции

```bash
alembic upgrade head
```

Проверка актуальности схемы:

```bash
alembic current
alembic check
```

### 7. Запустить приложение

```bash
uvicorn app.main:app --reload
```

Открой лендинг:

```text
http://127.0.0.1:8000/
```

Документация API:

```text
http://127.0.0.1:8000/docs
```

## Основные Сценарии

### Быстрый Скрининг По Вакансии

1. Открой главную страницу.
2. Введи имя и email.
3. Вставь публичную ссылку на вакансию.
4. Нажми `Разобрать вакансию`.
5. После извлечения требований нажми `Быстрый скрининг` или `Открыть живой чат`.
6. Отвечай на вопросы по одному.
7. После завершения получи рекомендации и при успешном результате перейди к техническому этапу.

Для быстрого скрининга резюме необязательно.

### Полный Сценарий С Резюме

1. Добавь вакансию.
2. Загрузи резюме в `PDF` или `DOCX`.
3. Система сопоставит требования вакансии и текст резюме.
4. Заполни ответы на уточняющие вопросы.
5. Отметь чекбоксами факты, которые можно добавить в новую версию CV.
6. Проверь AI-отредактированные факты и выбранные разделы резюме.
7. Создай новую версию резюме.
8. Отредактируй результат вручную.
9. Сохрани правки и скачай PDF.

### Живой Чат Интервью

На лендинге нажми `Открыть живой чат`.

В чате можно:

- выбрать режим интервью;
- отвечать текстом;
- надиктовывать ответ через кнопку `Записать голос`;
- отредактировать распознанный текст перед отправкой;
- завершить интервью в любой момент;
- получить подробный отчет и план подготовки.

## AI-Провайдеры

### OpenAI

Рекомендуется для реалистичного интервью, follow-up вопросов, анализа ответов и web research.

```env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1
```

В режиме OpenAI в облако могут передаваться:

- текст вакансии;
- извлеченный текст резюме;
- ответы на уточняющие вопросы;
- сообщения интервью;
- короткие аудиофайлы для транскрипции.

Проверить активный режим можно через:

```text
http://127.0.0.1:8000/privacy
```

### Ollama

Для локального режима:

```bash
ollama pull qwen2.5:7b
OLLAMA_NO_CLOUD=true ollama serve
```

Затем в `.env`:

```env
AI_PROVIDER=ollama
LOCAL_LLM_URL=http://127.0.0.1:11434
LOCAL_LLM_MODEL=qwen2.5:7b
```

В локальном режиме OpenAI не используется. Загрузка вакансии по URL остается внешним сетевым действием, если `REMOTE_VACANCY_FETCH_ENABLED=true`.

## Архитектура

```text
Browser
  |
  v
FastAPI
  |- Landing and interview chat pages
  |- Vacancy parser
  |- Resume parser
  |- Vacancy analyzer
  |- Resume matcher
  |- Clarification and CV generator
  |- Screening and interview engine
  |- PDF exporter
  |
  +--> PostgreSQL
  +--> OpenAI or Ollama
  +--> Public vacancy sites (optional)
```

### Структура Проекта

```text
app/
  main.py                 FastAPI routes
  models.py               SQLAlchemy models
  schemas.py              Pydantic request and response schemas
  database.py             Database session
  config.py               Environment configuration
  local_llm.py            AI provider adapter and workflows
  parsers.py              Resume and vacancy parsing
  pdf_export.py           PDF generation
  prompts/                Editable AI prompts
  static/                 Landing and interview chat UI
migrations/               Alembic migrations
requirements.txt
PRIVACY.md
```

## Prompts

Основные промпты находятся в `app/prompts/`:

- `vacancy_analyzer.py` - структурирование вакансии.
- `primary_screening.py` - быстрый скрининг и выбор тем.
- `qa_interview_screener.py` - живой QA-чат и финальный отчет.

Промпты можно менять без изменения API-логики. После изменения перезапусти FastAPI.

## Важные Таблицы

| Таблица | Назначение |
|---|---|
| `master_profiles` | Базовый профиль кандидата. |
| `resume_files` | Метаданные и извлеченный текст загруженных резюме. |
| `vacancies` | Исходные вакансии. |
| `vacancy_requirements` | Требования, подтвержденные текстом вакансии. |
| `vacancy_profiles` | Структурированный AI-анализ вакансии. |
| `applications` | Связь кандидата и вакансии. |
| `application_matches` | Результаты сопоставления CV и требований. |
| `clarification_questions` | Вопросы о неподтвержденном опыте. |
| `clarification_answers` | Исходные и отредактированные ответы кандидата. |
| `resume_versions` | Сгенерированные и вручную отредактированные CV. |
| `interview_sessions` | Скрининги, технические интервью и чат-сессии. |
| `interview_messages` | История сообщений, темы, баллы и feedback. |

## Ключевые API-Маршруты

| Метод | Маршрут | Назначение |
|---|---|---|
| `POST` | `/profiles` | Создать или обновить профиль по email. |
| `POST` | `/profiles/{profile_id}/resume` | Загрузить PDF/DOCX резюме. |
| `POST` | `/vacancies/from-url` | Скачать и проанализировать публичную вакансию. |
| `POST` | `/vacancies` | Сохранить вакансию, введенную вручную. |
| `POST` | `/applications` | Связать профиль и вакансию. |
| `POST` | `/applications/{id}/match` | Сопоставить CV и требования. |
| `POST` | `/applications/{id}/clarification-answers` | Сохранить и отредактировать уточняющие ответы. |
| `POST` | `/applications/{id}/resume/generate` | Создать новую версию резюме. |
| `PATCH` | `/resume-versions/{id}` | Сохранить ручные правки CV. |
| `GET` | `/resume-versions/{id}/export.pdf` | Скачать резюме в PDF. |
| `POST` | `/applications/{id}/screening/start` | Запустить быстрый скрининг. |
| `POST` | `/applications/{id}/interview-chat/start` | Начать живой чат. |
| `POST` | `/interview-chat/{id}/messages` | Отправить реплику в живой чат. |
| `POST` | `/interview-chat/{id}/transcribe` | Распознать голосовой ответ. |
| `POST` | `/interview-chat/{id}/complete` | Получить итоговый отчет. |
| `GET` | `/privacy` | Показать активный AI-режим и внешние потоки данных. |

## Проверка Базы Данных

Подключиться к PostgreSQL:

```bash
PGPASSWORD='qacv_password' psql -h localhost -p 5432 -U qacv -d qacv
```

Полезные команды:

```sql
\dt
SELECT id, title, source_url FROM vacancies;
SELECT id, name, email FROM master_profiles;
SELECT id, stage, mode, status FROM interview_sessions;
SELECT session_id, role, topic, score FROM interview_messages ORDER BY id;
```

## Troubleshooting

### `Address already in use` на порту 8000

Останови предыдущий FastAPI-процесс:

```bash
lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill
```

Затем запусти приложение снова:

```bash
uvicorn app.main:app --reload
```

### PostgreSQL не доступен

Проверь Docker:

```bash
docker ps -a
docker start qacv-postgres
```

### OpenAI возвращает `503`

Проверь:

- есть ли `OPENAI_API_KEY` в `.env`;
- установлен ли `AI_PROVIDER=openai`;
- доступна ли сеть;
- доступна ли указанная в `OPENAI_MODEL` модель для аккаунта.

После изменения `.env` всегда перезапускай FastAPI.

### Микрофон не работает

- используй `http://127.0.0.1:8000`, а не произвольный IP-адрес;
- разреши браузеру доступ к микрофону;
- проверь, что OpenAI API-ключ имеет доступ к transcription API.

### Миграции не применяются

```bash
alembic current
alembic upgrade head
```

## Приватность

- `.env`, загруженные резюме и база данных не коммитятся в Git.
- Резюме хранятся в `storage/resumes/`; эта папка исключена из Git.
- Полная схема потоков данных описана в [PRIVACY.md](PRIVACY.md).
- При `AI_PROVIDER=openai` данные AI-этапов отправляются OpenAI.
- При `AI_PROVIDER=ollama` AI-обработка остается на компьютере, кроме опционального получения вакансии по URL.

## Разработка

Перед коммитом:

```bash
python -m compileall app migrations
alembic check
node --check app/static/app.js
node --check app/static/interview.js
```

Создание следующей миграции:

```bash
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```
