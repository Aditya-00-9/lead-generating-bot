from app.prompts.collection_signals import text_has_pain_signal
from app.utils.platform import platform_from_url


def test_text_has_pain_signal_gate_keywords() -> None:
    assert text_has_pain_signal("We are switching from Mindbody next month")
    assert text_has_pain_signal("billing nightmare with Pike13")


def test_text_has_pain_signal_long_phrases() -> None:
    assert text_has_pain_signal("I'm frustrated with terrible support lately")


def test_text_has_pain_signal_negative() -> None:
    assert not text_has_pain_signal("Mindbody announced a new feature today")


def test_platform_from_url_g2() -> None:
    assert platform_from_url("https://www.g2.com/products/mystudio/reviews") == "g2"
