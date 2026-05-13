# ML Service — Заработок

## Назначение

Микросервис предсказания зарплат на основе ML-моделей. Принимает вектор профиля кандидата, возвращает квантильную вилку (p25, p50, p75) + SHAP-значения + контрфактуалы.

## Текущий статус

⚠️ **Используется заглушка (StubPredictor)** — детерминированные эвристики вместо реальной модели.

## API контракт

### `POST /predict`

**Request:**
```json
{
  "job_title": "Senior Python Developer",
  "experience_years": 5.0,
  "skills": ["Python", "FastAPI", "PostgreSQL"],
  "location": "Москва",
  "education_level": "bachelor"
}
```

**Response:**
```json
{
  "p25_salary": 120000,
  "p50_salary": 160000,
  "p75_salary": 216000,
  "shap_values": {
    "experience_years": 50000.0,
    "skills:Python": 10000.0,
    "location:Москва": 24000.0
  },
  "counterfactuals": [
    {
      "change_description": "Добавьте навык Rust",
      "feature_changed": "skills",
      "new_value": "Rust",
      "estimated_salary_increase": 23400
    }
  ]
}
```

## Инструкции для ML-разработчика

1. **Замените `StubPredictor`** в `app/predictor.py` на реальный инференс CatBoost/LightGBM
2. **Загрузка моделей**: поместите `.pkl` / `.onnx` файлы в `app/models/`, загружайте в `lifespan` хуке в `main.py`
3. **SHAP**: используйте `shap.TreeExplainer` для генерации SHAP-значений
4. **Контрфактуалы**: используйте DiCE для генерации путей улучшения
5. **НЕ меняйте `PredictionRequest` / `PredictionResponse`** в `app/schemas.py` без согласования с backend

## Запуск

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```
