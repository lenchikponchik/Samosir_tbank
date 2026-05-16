# Zarabotok Backend

MVP backend for salary-range analysis from a resume profile.

The current architecture follows the technical specification for the GPT-OSS flow:

- backend accepts and technically validates the resume profile;
- preflight builds `segment_key`, checks segment freshness, prepares `candidate_vacancies`, and calculates `request_hash`;
- one unique `request_hash` allows at most one model call;
- the model service receives profile + segment + candidate vacancies in one payload;
- backend validates only JSON shape and linkage with the input payload, then saves valid or failed output in `llm_salary_results`;
- salary quantiles, salary range, matched/missing skills, factor analysis, and recommendations are produced by the model service, not by backend logic.

## Main API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/analyze` | Main MVP endpoint: preflight + cache + one GPT-OSS-compatible call |
| POST | `/api/v1/resumes` | Create a saved resume draft |
| GET | `/api/v1/resumes/{id}` | Read a saved resume draft |
| PATCH | `/api/v1/resumes/{id}` | Update a saved resume draft |
| GET | `/health` | Backend healthcheck |

Example request:

```json
{
  "profile": {
    "title": "Python Backend Developer",
    "experience_years": 3,
    "location": "Москва",
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "resume_text": "Разрабатывал backend-сервисы на FastAPI...",
    "current_salary": 150000
  },
  "options": {
    "target_salary": 250000,
    "force_refresh": false
  }
}
```

## Model Integration

`ml_service` currently exposes a temporary `/analyze` stub with the GPT-OSS-compatible JSON contract. When the real model is ready, replace that endpoint or point backend to another service with:

```env
GPT_OSS_SERVICE_URL=http://ml_service:8001
GPT_OSS_ANALYZE_PATH=/analyze
GPT_OSS_MODEL_NAME=gpt-oss-20b
GPT_OSS_MODEL_VERSION=gpt-oss-20b-salary-v1
GPT_OSS_PROMPT_VERSION=salary_prompt_v1
```

Backend must not add fallback salary heuristics. If the model returns invalid JSON, backend saves the failed result and returns `LLM_OUTPUT_VALIDATION_FAILED` without retrying.

## Database Tables Added For The Spec

- `market_segments`
- `vacancies`
- `llm_salary_results`

Existing legacy tables are kept for compatibility, but the public v1 router now exposes the GPT-OSS analyze flow instead of the old `/estimates` pipeline.

## Local Start

```bash
cp .env.example .env
docker-compose up --build
```

API docs:

```text
http://localhost:8000/docs
```

Seed local test vacancies:

```bash
docker-compose exec backend alembic upgrade head
docker-compose exec backend python -m app.seed_test_data
```

Then this demo profile should hit the seeded backend segment:

```json
{
  "profile": {
    "title": "Python Backend Developer",
    "experience_years": 3,
    "location": "Москва",
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "resume_text": "Разрабатывал backend-сервисы на FastAPI.",
    "current_salary": 150000
  },
  "options": {
    "target_salary": 250000,
    "force_refresh": false
  }
}
```

Run tests:

```bash
cd backend
python -m pytest

cd ../ml_service
python -m pytest
```
