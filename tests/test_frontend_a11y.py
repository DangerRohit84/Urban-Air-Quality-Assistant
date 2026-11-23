"""Accessibility tests for the frontend shell.

The checks are deliberately structural: they parse ``index.html``, ``styles.css``
and the native ES modules under ``frontend/js`` with the standard library so the
accessibility contract is enforced without a browser or a new dependency.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
INDEX = FRONTEND / "index.html"
STYLES = FRONTEND / "styles.css"
MODULES = FRONTEND / "js"
SECURITY_POLICY_URL = (
    "https://github.com/DangerRohit84/Urban-Air-Quality-Assistant/security/policy"
)

FORM_CONTROL_TAGS = {"input", "select", "textarea"}
CONTROL_TAGS = FORM_CONTROL_TAGS | {"button"}


class _ElementParser(HTMLParser):
    """Collect start tags, ids and label ``for`` targets."""

    def __init__(self) -> None:
        """Initialise the collected element list and id/label indexes."""
        super().__init__(convert_charrefs=True)
        self.elements: list[dict[str, str]] = []
        self.ids: set[str] = set()
        self.labels: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record one start tag.

        Args:
            tag: The element name.
            attrs: The element attributes.
        """
        attr = {key: value or "" for key, value in attrs}
        self.elements.append({"tag": tag, **attr})
        if "id" in attr:
            self.ids.add(attr["id"])
        if tag == "label" and attr.get("for"):
            self.labels.add(attr["for"])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record a self-closing tag.

        Args:
            tag: The element name.
            attrs: The element attributes.
        """
        self.handle_starttag(tag, attrs)


def _parse_index() -> _ElementParser:
    """Parse ``index.html`` into an element index.

    Returns:
        The populated parser.
    """
    parser = _ElementParser()
    parser.feed(INDEX.read_text(encoding="utf-8"))
    parser.close()
    return parser


def _by_id(parsed: _ElementParser) -> dict[str, dict[str, str]]:
    """Return the parsed elements keyed by id.

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


def test_every_form_control_has_an_id_and_a_label() -> None:
    """Every input, select and textarea carries an id and a matching label."""
    parsed = _parse_index()
    controls = [
        element for element in parsed.elements if element["tag"] in FORM_CONTROL_TAGS
    ]

    assert controls, "the shell exposes no form controls"
    for element in controls:
        control_id = element.get("id", "")
        assert control_id, f"<{element['tag']}> has no id"
        assert control_id in parsed.labels, f"<{control_id}> has no <label for>"

    by_id = _by_id(parsed)
    for email_id in ("reg-email", "login-email"):
        assert by_id[email_id]["autocomplete"] == "email"
        assert by_id[email_id]["inputmode"] == "email"
        assert by_id[email_id]["spellcheck"] == "false"
    assert by_id["reg-password"]["autocomplete"] == "new-password"
    assert by_id["login-password"]["autocomplete"] == "current-password"
    for password_id in ("reg-password", "login-password"):
        assert by_id[password_id]["spellcheck"] == "false"


def test_every_control_has_aria_describedby_pointing_at_an_existing_id() -> None:
    """Every control references at least one existing description id."""
    parsed = _parse_index()
    controls = [
        element for element in parsed.elements if element["tag"] in CONTROL_TAGS
    ]

    assert controls, "the shell exposes no controls"
    for element in controls:
        described_by = element.get("aria-describedby", "")
        assert described_by, f"<{element['tag']}>#{element.get('id')} has no hint"
        for target in described_by.split():
            assert target in parsed.ids, f"#{target} does not exist"


def test_live_regions_are_marked_up() -> None:
    """Status, error and answer regions are announced to assistive technology."""
    by_id = _by_id(_parse_index())

    assert by_id["status"]["role"] == "status"
    assert by_id["status"]["aria-live"] == "polite"
    assert by_id["errors"]["role"] == "alert"
    assert by_id["errors"]["aria-live"] == "assertive"
    assert by_id["errors"]["tabindex"] == "-1"
    assert by_id["answer"]["aria-live"] == "polite"


def test_skip_link_landmarks_and_noscript() -> None:
    """The shell has a skip link, landmarks and a noscript fallback."""
    parsed = _parse_index()

    tags = {element["tag"] for element in parsed.elements}
    roles = {element.get("role", "") for element in parsed.elements}
    assert "noscript" in tags
    assert any(
        element["tag"] == "a" and element.get("href") == "#main"
        for element in parsed.elements
    )
    assert {"banner", "main", "contentinfo"} <= roles
    assert {"header", "main", "footer"} <= tags

    security_links = [
        element
        for element in parsed.elements
        if element["tag"] == "a" and element.get("href") == SECURITY_POLICY_URL
    ]
    assert security_links, "the footer does not link the security policy"
    assert security_links[0]["target"] == "_blank"
    assert "noopener" in security_links[0]["rel"]
    assert "noreferrer" in security_links[0]["rel"]


def test_styles_document_contrast_targets_and_reduced_motion() -> None:
    """The stylesheet documents AA contrast, 44px targets and reduced motion."""
    css = STYLES.read_text(encoding="utf-8")

    assert "CONTRAST RATIOS" in css
    assert "4.5:1" in css
    assert "3:1" in css
    assert "--border-strong" in css
    assert "min-height: 44px" in css
    assert "min-width: 44px" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def _css_block(css: str, selector: str) -> str:
    """Return the declaration block for ``selector``.

    Args:
        css: The stylesheet text.
        selector: The selector to locate.

    Returns:
        The declarations between the selector's braces.
    """
    start = css.index(selector + " {")
    opening = css.index("{", start)
    closing = css.index("}", opening)
    return css[opening + 1 : closing]


def test_checkbox_touch_target_is_a_44px_composite_label() -> None:
    """The 24px checkbox rides on a 44px clickable label target."""
    css = STYLES.read_text(encoding="utf-8")

    input_block = _css_block(css, ".field.checkbox input")
    label_block = _css_block(css, ".field.checkbox label")

    assert "width: 24px" in input_block
    assert "min-height: 44px" in label_block
    assert "min-width: 44px" in label_block


def test_modules_are_text_content_only_and_expose_helpers() -> None:
    """The modules never parse HTML and expose the shared scaffold helpers."""
    sources = _module_sources()
    assert sources, "the frontend exposes no JavaScript modules"
    javascript = "\n".join(sources.values())

    for banned in ("innerHTML", "insertAdjacentHTML", "outerHTML"):
        assert banned not in javascript
    assert "textContent" in javascript
    for helper in ("apiFetch", "showStatus", "showError", "focusErrors"):
        assert f"function {helper}" in javascript
    for path, source in sources.items():
        assert "/**" in source, f"{path.name} lacks JSDoc"

    parsed = _parse_index()
    scripts = [element for element in parsed.elements if element["tag"] == "script"]
    assert len(scripts) == 1
    assert scripts[0]["type"] == "module"
    assert scripts[0]["src"] == "/static/js/main.js"
    assert not (FRONTEND / "app.js").exists()
