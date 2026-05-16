# GPT-OSS-Compatible Model Service

This service is the replaceable model boundary for the backend.

The important endpoint for the MVP is:

```text
POST /analyze
```

Backend sends one payload containing:

- `request_hash`
- `profile`
- `segment`
- `candidate_vacancies`
- `rules`

The service must return the strict GPT-OSS salary result JSON:

- `market_sample`
- `salary_range`
- `confidence`
- `matched_skills`
- `missing_skills`
- `factor_analysis`
- `recommendations`

The current implementation is a local stub so the backend contract can be tested before the real `gpt-oss-20b` integration is ready. The real model should replace `StubPredictor.analyze()` in `app/predictor.py` while keeping the response shape stable.

`POST /predict` is still present only as a legacy compatibility endpoint for old tests/scripts. New backend code uses `/analyze`.

Run locally:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```
