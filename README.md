# Заработок — Backend

Сервис предиктивной оценки и оптимизации резюме. Предсказывает рыночную вилку зарплат на основе ML и генерирует персонализированные рекомендации по улучшению резюме.

## Архитектура

```
┌─────────┐     ┌──────────┐     ┌────────────┐
│  Nginx  │────▶│  FastAPI  │────▶│ ML Service │
│  :80    │     │  :8000   │     │  :8001     │
└─────────┘     └────┬─────┘     └────────────┘
                     │
              ┌──────┴──────┐
              │             │
        ┌─────▼──┐   ┌─────▼──┐
        │Postgres│   │ Redis  │
        │ :5432  │   │ :6379  │
        └────────┘   └────────┘
```

## Быстрый старт

```bash
# 1. Скопировать и настроить переменные окружения
cp .env.example .env

# 2. Запустить все сервисы
docker-compose up --build

# 3. Открыть документацию API
# http://localhost:8000/docs
```

## API эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/v1/resumes` | Создать резюме |
| GET | `/api/v1/resumes/{id}` | Получить резюме |
| PATCH | `/api/v1/resumes/{id}` | Обновить резюме |
| POST | `/api/v1/estimates` | Оценить зарплату (новый профиль) |
| POST | `/api/v1/estimates/resume/{id}` | Пересчитать (итеративное улучшение) |
| GET | `/api/v1/estimates/{id}` | Получить сохранённую оценку |
| GET | `/api/v1/recommendations/estimate/{id}` | Рекомендации по оценке |
| GET | `/api/v1/history/resume/{id}` | История эволюции вилки |

## Технологический стек

- **Backend**: Python 3.11, FastAPI, Pydantic v2
- **ORM**: SQLAlchemy 2.0 (async) + Alembic
- **БД**: PostgreSQL 15 (JSONB, PL/pgSQL триггеры)
- **Кеш**: Redis 7
- **ML**: CatBoost / LightGBM (заглушка на старте)
- **LLM**: Anthropic Claude (генерация рекомендаций)
- **Инфра**: Docker, Docker Compose, Nginx

## Структура проекта

```
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/v1/   # REST API роутеры
│   │   ├── models/   # SQLAlchemy ORM
│   │   ├── schemas/  # Pydantic контракты
│   │   ├── services/ # Бизнес-логика
│   │   └── db/       # Database session
│   └── alembic/      # Миграции БД
├── ml_service/       # ML микросервис (заглушка)
├── nginx/            # Reverse proxy
└── docker-compose.yml
```

## Миграции БД

```bash
# Применить миграции
cd backend
alembic upgrade head

# Откатить
alembic downgrade -1
```