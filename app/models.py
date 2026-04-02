from pydantic import BaseModel, HttpUrl


# --- Request models ---
# These define what the caller must send in the request body.
# Pydantic validates the data automatically before your endpoint function runs.

class UrlRequest(BaseModel):
    url: HttpUrl  # HttpUrl type validates that the string is a real URL (has scheme + host)

class HtmlRequest(BaseModel):
    html: str
    base_url: str | None = None  # optional — helps resolve relative image/script URLs


# --- Internal models ---

class AnalyzerResult(BaseModel):
    """The output of a single analyzer. Each analyzer returns one of these."""
    score: int           # 0–100
    weight: float        # how much this analyzer contributes to the final score
    evidence: list[str]  # human-readable list of signals that fired


# --- Response model ---

class AnalysisResponse(BaseModel):
    """The full API response returned to the caller."""
    score: int           # final weighted score 0–100
    label: str           # e.g. "Likely AI", "Human-built"
    breakdown: dict[str, AnalyzerResult]  # one entry per analyzer
    stack: list[str]      # underlying stack the website is using
