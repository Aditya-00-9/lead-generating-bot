from app.models.schemas import AIEnrichmentResult


def test_enrichment_schema_validates() -> None:
    payload = {
        "competitor": "MyStudio",
        "detected_pain_points": ["pricing"],
        "intent_score": 82.0,
        "intent_label": "HIGH",
        "worth_responding": True,
        "ai_summary": "User is unhappy with pricing and seeking alternatives.",
        "suggested_reply": "We faced similar pricing pressure. Curious what pricing model would make the switch worthwhile for you?",
        "sentiment": "negative",
        "urgency_score": 75.0,
        "engagement_score": 61.0,
        "tags": ["pricing", "switch-intent"],
    }
    obj = AIEnrichmentResult.model_validate(payload)
    assert obj.intent_label.value == "HIGH"
