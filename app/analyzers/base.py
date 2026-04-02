from abc import ABC, abstractmethod
from app.models import AnalyzerResult


class BaseAnalyzer(ABC):
    """
    Abstract base class for all analyzers.

    ABC = Abstract Base Class. Any class that inherits from this
    MUST implement the `analyze` method, or Python will raise a
    TypeError when you try to instantiate it.

    This pattern enforces a consistent interface across all analyzers —
    the scorer can call .analyze() on any of them without caring which
    one it's talking to.
    """

    @property
    @abstractmethod
    def weight(self) -> float:
        """Each analyzer declares its own contribution weight (0.0–1.0)."""

    @abstractmethod
    def analyze(self, html: str) -> AnalyzerResult:
        """
        Parse the HTML and return a score + evidence.
        All subclasses must implement this.
        """
