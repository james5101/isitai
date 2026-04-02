import httpx
from bs4 import BeautifulSoup
from app.analyzers.base import BaseAnalyzer
from app.models import AnalyzerResult
from app import config

_HF_URL = "https://router.huggingface.co/hf-inference/models/openai-community/roberta-large-openai-detector"
_MIN_TEXT_LENGTH = 250  # model needs enough text for a reliable prediction


def _extract_text(html: str) -> str:
    """Pull visible text from HTML, stripping scripts/styles/nav."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "head"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


def _parse_fake_score(data: list) -> float:
    """
    Extract the AI probability from the HuggingFace response.

    The model returns a list of {label, score} dicts. Labels are "Real"
    (human-written) and "Fake" (AI-generated). We want the "Fake" score.

    Response shape: [{"label": "Real", "score": 0.85}, {"label": "Fake", "score": 0.15}]
    HF sometimes wraps this in an outer list: [[{...}, {...}]]
    """
    # Unwrap outer list if present
    if data and isinstance(data[0], list):
        data = data[0]

    for item in data:
        label = item.get("label", "").lower()
        if label in ("fake", "label_1"):
            return item["score"]

    raise ValueError(f"Could not find 'Fake' label in response: {data}")


class AiTextAnalyzer(BaseAnalyzer):
    """
    Uses the HuggingFace roberta-large-openai-detector model to score
    how likely the page text is AI-generated.

    The model was trained by OpenAI to detect GPT-2 output, and generalizes
    reasonably well to other LLM-generated text. It returns a "Fake" probability
    (0.0–1.0) which we scale to 0–100.

    Optional: if HF_API_KEY is not set in .env, weight=0.0 and this
    analyzer is excluded from scoring.

    Weight when active: 0.35
    """

    @property
    def weight(self) -> float:
        return 0.35

    def analyze(self, html: str) -> AnalyzerResult:
        if not config.HF_API_KEY:
            return AnalyzerResult(
                score=0,
                weight=0.0,
                evidence=["HuggingFace API key not configured — skipped"],
            )

        text = _extract_text(html)

        if len(text) < _MIN_TEXT_LENGTH:
            return AnalyzerResult(
                score=0,
                weight=0.0,
                evidence=["Not enough text for AI text analysis (min 250 chars)"],
            )

        try:
            with httpx.Client(timeout=30.0) as client:  # model may need warm-up time
                response = client.post(
                    _HF_URL,
                    headers={"Authorization": f"Bearer {config.HF_API_KEY}"},
                    json={"inputs": text[:500]},  # roberta-large max is 512 tokens; 500 chars is reliably safe
                )
                response.raise_for_status()

            fake_prob = _parse_fake_score(response.json())
            score = min(100, int(fake_prob * 100))

            return AnalyzerResult(
                score=score,
                weight=self.weight,
                evidence=[f"roberta-large-openai-detector: {fake_prob:.0%} probability of AI-generated text"],
            )

        except httpx.HTTPStatusError as e:
            body = e.response.text[:200]
            return AnalyzerResult(
                score=0,
                weight=0.0,
                evidence=[f"HuggingFace API error {e.response.status_code}: {body}"],
            )
        except (httpx.HTTPError, KeyError, ValueError) as e:
            return AnalyzerResult(
                score=0,
                weight=0.0,
                evidence=[f"AI text API error (skipped): {type(e).__name__}: {e}"],
            )
