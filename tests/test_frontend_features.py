"""Feature tests for the frontend wiring.

The checks parse ``index.html`` and the native ES modules under ``frontend/js``
with the standard library so the feature contract (endpoints, sections, live
regions) is enforced without a browser or a new dependency.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
INDEX = FRONTEND / "index.html"
MODULES = FRONTEND / "js"

CPCB_BANDS = (
    "Good",
    "Satisfactory",
    "Moderately Polluted",
    "Poor",
    "Very Poor",
    "Severe",
)

DYNAMIC_REGIONS = (
    "status",
    "errors",
    "answer",
    "answerMode",
    "citations",
    "uploadStatus",
    "docs-list",
    "plans-routines",
    "plans-hacks",
    "plans-alternatives",
    "impact",
    "aqi-readout",
)


class _ElementParser(HTMLParser):
    """Collect start tags and their attributes."""

    def __init__(self) -> None:
        """Initialise the element list."""
        super().__init__(convert_charrefs=True)
        self.elements: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record one start tag.

        Args:
            tag: The element name.
            attrs: The element attributes.
        """
        self.elements.append({"tag": tag, **{k: v or "" for k, v in attrs}})

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record a self-closing tag.

        Args:
            tag: The element name.
            attrs: The element attributes.
        """
        self.handle_starttag(tag, attrs)


def _parse_index() -> _ElementParser:
    """Parse ``index.html``.

    Returns:
        The populated parser.
    """
    parser = _ElementParser()
    parser.feed(INDEX.read_text(encoding="utf-8"))
    parser.close()
    return parser


def _by_id(parsed: _ElementParser) -> dict[str, dict[str, str]]:
    """Return parsed elements keyed by id.

    Args:
        parsed: The parsed document.

    Returns:
        A mapping of id to element attributes.
    """
    return {element["id"]: element for element in parsed.elements if element.get("id")}


def _module_sources() -> dict[Path, str]:
    """Return every frontend module's source keyed by path.

    Returns:
        A mapping of module path to UTF-8 source text.
    """
    return {
        path: path.read_text(encoding="utf-8")
        for path in sorted(MODULES.glob("**/*.js"))
    }


def _all_source() -> str:
    """Return every frontend module's source joined for whole-app assertions.

    Returns:
        The concatenated module sources.
    """
    return "\n".join(_module_sources().values())


def _function_source(name: str) -> str:
    """Return the body of a top-level ``function`` in the frontend modules.

    Args:
        name: The function name.

    Returns:
        The braces-delimited function body.
    """
    for source in _module_sources().values():
        marker = f"function {name}("
        if marker not in source:
            continue
        start = source.index(marker)
        opening = source.index("{", start)
        depth = 0
        for index in range(opening, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    return source[opening : index + 1]
    raise AssertionError(f"function {name} not found in frontend modules")


def test_aqi_band_lists_the_six_cpcb_bands() -> None:
    """The band select offers exactly the six CPCB band names."""
    by_id = _by_id(_parse_index())

    assert by_id["aqi-band"]["tag"] == "select"
    parser = _ElementParser()
    parser.feed(INDEX.read_text(encoding="utf-8"))
    options = [
        element["value"]
        for element in parser.elements
        if element["tag"] == "option" and element.get("value") in CPCB_BANDS
    ]

    assert tuple(option for option in options if option) == CPCB_BANDS


def test_fetch_live_button_is_wired_to_the_air_endpoint() -> None:
    """The live button exists and its handler calls ``/air?q=``."""
    by_id = _by_id(_parse_index())
    source = _all_source()

    assert by_id["fetch-live"]["tag"] == "button"
    assert 'getElementById("fetch-live")' in source
    assert "/air?q=" in source
    assert "function fetchLiveAqi" in source


def test_render_plans_populates_all_three_sections() -> None:
    """``renderPlans`` reads the three payload sections into the page."""
    body = _function_source("renderPlans")

    for section in ("routines", "hacks", "alternatives"):
        assert section in body
    for element_id in ("plans-routines", "plans-hacks", "plans-alternatives"):
        assert element_id in body


def test_render_impact_writes_the_three_metrics() -> None:
    """``renderImpact`` writes the metric spans through ``textContent``."""
    body = _function_source("renderImpact")

    for element_id in ("impact-co2e", "impact-exposure", "impact-cost"):
        assert element_id in body
    assert "textContent" in body


def test_ask_question_sends_question_and_plain_flag() -> None:
    """``askQuestion`` posts the question and reads ``#plain.checked``."""
    body = _function_source("askQuestion")

    assert "question" in body
    assert "plain_language" in body
    assert "body: { question, plain_language: plain }," in body
    assert '"plain"' in body
    assert ".checked" in body


def test_documents_target_the_document_endpoints() -> None:
    """The document functions target the list and upload endpoints."""
    assert '"/documents"' in _function_source("loadDocuments")
    assert '"/documents/upload"' in _function_source("uploadDocument")


def test_export_button_targets_markdown_export() -> None:
    """The export button targets ``/export?format=md``."""
    source = _all_source()

    assert 'getElementById("exportBtn")' in source
    assert "/export?format=md" in source


def test_no_html_parsing_anywhere() -> None:
    """The modules never assign through ``innerHTML`` or a sibling API."""
    source = _all_source()

    for banned in ("innerHTML", "insertAdjacentHTML", "outerHTML"):
        assert banned not in source


def test_every_dynamic_region_is_a_live_region() -> None:
    """Every region the modules write to is announced to assistive technology."""
    by_id = _by_id(_parse_index())

    for region in DYNAMIC_REGIONS:
        element = by_id[region]
        assert element.get("aria-live") or element.get("role") in {
            "status",
            "alert",
        }, f"#{region} is not a live region"
