import pytest
from unittest.mock import patch, MagicMock
import httpx
from app.analyzers.ai_text import AiTextAnalyzer

# Enough text to pass the 250-char minimum check (must be >250 chars AFTER BeautifulSoup strips HTML)
_LONG_HTML = """<html><body><p>
    We leverage cutting-edge, innovative solutions to empower your business and streamline
    your workflow in today's digital landscape. Our seamless platform elevates your brand
    and drives results. Unlock your potential with our world-class, end-to-end comprehensive
    solutions tailored to your specific needs. Transform your business with our holistic,
    game-changing approach designed for modern enterprises seeking scalable growth.
</p></body></html>"""

_SHORT_HTML = "<html><body><p>Too short.</p></body></html>"


def _make_mock_response(fake_score: float) -> MagicMock:
    """Build a fake HuggingFace response with the given Fake/Real scores."""
    mock = MagicMock()
    mock.json.return_value = [
        {"label": "Real", "score": round(1.0 - fake_score, 4)},
        {"label": "Fake", "score": fake_score},
    ]
    mock.raise_for_status = MagicMock()
    return mock


# --- Tests ---

def test_no_api_key_returns_weight_zero():
    """When no API key is configured, analyzer must opt out (weight=0)."""
    with patch("app.analyzers.ai_text.config.HF_API_KEY", None):
        result = AiTextAnalyzer().analyze(_LONG_HTML)
    assert result.weight == 0.0
    assert result.score == 0
    assert "not configured" in result.evidence[0]


def test_high_fake_score():
    """Model returns 92% Fake probability → score should be 92."""
    with patch("app.analyzers.ai_text.config.HF_API_KEY", "fake-key"), \
         patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.post.return_value = \
            _make_mock_response(0.92)
        result = AiTextAnalyzer().analyze(_LONG_HTML)

    assert result.score == 92
    assert result.weight == 0.35
    assert "92%" in result.evidence[0]


def test_low_fake_score():
    """Model returns 8% Fake probability → score should be 8."""
    with patch("app.analyzers.ai_text.config.HF_API_KEY", "fake-key"), \
         patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.post.return_value = \
            _make_mock_response(0.08)
        result = AiTextAnalyzer().analyze(_LONG_HTML)

    assert result.score == 8
    assert result.weight == 0.35


def test_short_text_abstains():
    """Text under 250 chars should be skipped (weight=0), not sent to the API."""
    with patch("app.analyzers.ai_text.config.HF_API_KEY", "fake-key"), \
         patch("httpx.Client") as mock_client_cls:
        result = AiTextAnalyzer().analyze(_SHORT_HTML)

    mock_client_cls.assert_not_called()
    assert result.weight == 0.0


def test_api_error_handled_gracefully():
    """A network error should not crash the analyzer — degrade to weight=0."""
    with patch("app.analyzers.ai_text.config.HF_API_KEY", "fake-key"), \
         patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.post.side_effect = \
            httpx.ConnectError("connection refused")
        result = AiTextAnalyzer().analyze(_LONG_HTML)

    assert result.score == 0
    assert result.weight == 0.0
    assert "error" in result.evidence[0].lower()


def test_nested_response_format():
    """HuggingFace sometimes wraps results in an outer list — handle both shapes."""
    with patch("app.analyzers.ai_text.config.HF_API_KEY", "fake-key"), \
         patch("httpx.Client") as mock_client_cls:
        mock = MagicMock()
        # Outer-list wrapped format
        mock.json.return_value = [[
            {"label": "Real", "score": 0.3},
            {"label": "Fake", "score": 0.7},
        ]]
        mock.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock
        result = AiTextAnalyzer().analyze(_LONG_HTML)

    assert result.score == 70


def test_numeric_label_format():
    """Model sometimes returns LABEL_1/LABEL_0 instead of Fake/Real — handle both."""
    with patch("app.analyzers.ai_text.config.HF_API_KEY", "fake-key"), \
         patch("httpx.Client") as mock_client_cls:
        mock = MagicMock()
        mock.json.return_value = [
            {"label": "LABEL_1", "score": 0.9989},
            {"label": "LABEL_0", "score": 0.0011},
        ]
        mock.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock
        result = AiTextAnalyzer().analyze(_LONG_HTML)

    assert result.score == 99


def test_weight_property():
    assert AiTextAnalyzer().weight == 0.35
