# Data flow

Only `POST /vacancies/from-url` accesses the external network. It downloads a public vacancy page when `REMOTE_VACANCY_FETCH_ENABLED=true`, then stores the extracted vacancy locally.

The following data remains on the local computer:

- uploaded PDF and DOCX resumes in `storage/resumes/`;
- resume text, profiles, vacancies, applications, and interviews in local PostgreSQL;
- AI prompts and responses sent to Ollama at `http://127.0.0.1:11434`.

Set `REMOTE_VACANCY_FETCH_ENABLED=false` in `.env` to disable external fetching. Use `POST /vacancies` to paste a vacancy manually instead.

`LOCAL_LLM_URL` is validated at application startup and can only use `127.0.0.1` or `::1`. Cloud AI endpoints are rejected.
