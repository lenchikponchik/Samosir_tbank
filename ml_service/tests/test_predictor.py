"""Tests for ML Service stub predictor."""

import pytest
from app.schemas import PredictionRequest, PredictionResponse, Counterfactual
from app.predictor import StubPredictor


class TestStubPredictor:
    @pytest.fixture
    def predictor(self):
        return StubPredictor()

    def test_basic_prediction(self, predictor):
        req = PredictionRequest(
            job_title="Senior Python Developer",
            experience_years=5.0,
            skills=["Python", "FastAPI", "PostgreSQL"],
            location="Москва",
            education_level="bachelor",
        )
        result = predictor.predict(req)
        assert isinstance(result, PredictionResponse)
        assert result.p25_salary < result.p50_salary < result.p75_salary

    def test_moscow_pays_more(self, predictor):
        base = dict(job_title="Developer", experience_years=3.0, skills=["Python"])
        moscow = predictor.predict(PredictionRequest(**base, location="Москва"))
        kazan = predictor.predict(PredictionRequest(**base, location="Казань"))
        assert moscow.p50_salary > kazan.p50_salary

    def test_senior_earns_more(self, predictor):
        base = dict(skills=["Python"], location="Москва")
        senior = predictor.predict(PredictionRequest(job_title="Senior Dev", experience_years=5.0, **base))
        junior = predictor.predict(PredictionRequest(job_title="Junior Dev", experience_years=1.0, **base))
        assert senior.p50_salary > junior.p50_salary

    def test_more_skills_higher_salary(self, predictor):
        base = dict(job_title="Developer", experience_years=3.0, location="Москва")
        few = predictor.predict(PredictionRequest(**base, skills=["Python"]))
        many = predictor.predict(PredictionRequest(**base, skills=["Python", "Docker", "Kubernetes", "AWS"]))
        assert many.p50_salary > few.p50_salary

    def test_shap_values_present(self, predictor):
        req = PredictionRequest(job_title="Dev", experience_years=3.0, skills=["Python", "Docker"], location="Москва", education_level="master")
        result = predictor.predict(req)
        assert "experience_years" in result.shap_values
        assert "skills:Python" in result.shap_values
        assert "education:master" in result.shap_values

    def test_counterfactuals_generated(self, predictor):
        req = PredictionRequest(job_title="Dev", experience_years=3.0, skills=["Python"], location="Москва")
        result = predictor.predict(req)
        assert 0 < len(result.counterfactuals) <= 3
        for cf in result.counterfactuals:
            assert isinstance(cf, Counterfactual)
            assert cf.new_value.lower() != "python"

    def test_education_bonus(self, predictor):
        base = dict(job_title="Dev", experience_years=3.0, skills=["Python"], location="Москва")
        none_edu = predictor.predict(PredictionRequest(**base, education_level="none"))
        phd = predictor.predict(PredictionRequest(**base, education_level="phd"))
        assert phd.p50_salary > none_edu.p50_salary

    def test_zero_experience_valid(self, predictor):
        req = PredictionRequest(job_title="Junior", experience_years=0, skills=["Python"], location="Москва")
        result = predictor.predict(req)
        assert result.p50_salary > 0
