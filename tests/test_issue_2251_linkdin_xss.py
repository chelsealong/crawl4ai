"""Regression tests for issue #2251's LinkedIn demo DOM-XSS sinks.

Untrusted graph, profile, and model data must enter the page through DOM text
and URL properties. Markdown is the sole intentional HTML path and is sanitized
with DOMPurify before insertion.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

TEMPLATE = (
    Path(__file__).parent.parent
    / "docs"
    / "apps"
    / "linkdin"
    / "templates"
    / "graph_view_template.html"
)


def _html() -> str:
    return TEMPLATE.read_text()


def _main_script() -> str:
    scripts = re.findall(r"<script>(.*?)</script>", _html(), re.S)
    assert scripts, "no inline <script> block found in template"
    return scripts[-1]


def _extract_function(name: str) -> str:
    match = re.search(
        rf"function {name}\([^\n]*\) \{{.*?\n        \}}",
        _main_script(),
        re.S,
    )
    assert match, f"{name}() helper not found in template script"
    return match.group(0)


def _has_node() -> bool:
    try:
        return (
            subprocess.run(["node", "--version"], capture_output=True).returncode == 0
        )
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _has_node(), reason="node is required to execute safeUrl")
@pytest.mark.parametrize(
    "payload",
    [
        "javascript:alert(document.cookie)",
        "JaVaScRiPt:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
    ],
)
def test_safe_url_blocks_dangerous_schemes(payload):
    node_src = _extract_function("safeUrl") + (
        f"\nconsole.log(JSON.stringify(safeUrl({payload!r})));\n"
    )
    result = subprocess.run(
        ["node", "-e", node_src], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '"#"'


@pytest.mark.skipif(not _has_node(), reason="node is required to execute safeUrl")
@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("https://www.linkedin.com/in/example", "https://www.linkedin.com/in/example"),
        ("http://www.linkedin.com/in/example", "http://www.linkedin.com/in/example"),
    ],
)
def test_safe_url_allows_and_normalizes_http_urls(payload, expected):
    node_src = _extract_function("safeUrl") + (
        f"\nconsole.log(JSON.stringify(safeUrl({payload!r})));\n"
    )
    result = subprocess.run(
        ["node", "-e", node_src], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected


@pytest.mark.skipif(not _has_node(), reason="node is required to execute safeUrl")
def test_safe_url_resolves_relative_profile_against_explicit_base():
    node_src = _extract_function("safeUrl") + (
        "\nconsole.log(JSON.stringify(safeUrl('/in/example', '#', "
        "'https://www.linkedin.com/')));\n"
    )
    result = subprocess.run(
        ["node", "-e", node_src], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == "https://www.linkedin.com/in/example"


@pytest.mark.skipif(
    not _has_node(), reason="node is required to execute appendTextWithBreaks"
)
def test_stream_chunks_are_appended_as_text_nodes():
    payload = '<img src=x onerror="alert(1)">\nnext'
    node_src = f"""
const appended = [];
globalThis.document = {{
  createElement: tag => ({{ kind: tag }}),
  createTextNode: text => ({{ kind: 'text', text }})
}};
const container = {{ appendChild: node => appended.push(node) }};
{_extract_function("appendTextWithBreaks")}
appendTextWithBreaks(container, {payload!r});
console.log(JSON.stringify(appended));
"""
    result = subprocess.run(
        ["node", "-e", node_src], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        {"kind": "text", "text": '<img src=x onerror="alert(1)">'},
        {"kind": "br"},
        {"kind": "text", "text": "next"},
    ]


def _inner_html_template_after(marker: str) -> str:
    source = _main_script().split(marker, 1)[1]
    match = re.search(r"innerHTML = `(.*?)`", source, re.S)
    assert match, f"innerHTML template not found after {marker!r}"
    return match.group(1)


@pytest.mark.parametrize(
    "marker",
    [
        "data.nodes.forEach(n =>",
        "function renderOrg(chart, pane)",
        "decisionMakers.forEach(person =>",
        "function showPersonDetails(p)",
        "network.on('hoverNode'",
    ],
)
def test_structural_inner_html_templates_contain_no_dynamic_interpolation(marker):
    """Static skeletons may use innerHTML; untrusted values may not enter them."""
    assert "${" not in _inner_html_template_after(marker)


DOM_ASSIGNMENTS = [
    # Company list, including the previously missed followers field.
    "li.querySelector('[data-field=\"company-name\"]').textContent = n.name",
    "li.querySelector('[data-field=\"company-industry\"]').textContent = n.industry",
    "li.querySelector('[data-field=\"company-about\"]').textContent = n.about",
    "li.querySelector('[data-field=\"company-followers\"]').textContent",
    "li.querySelector('[data-field=\"company-link\"]').href = safeUrl(",
    # Org panel and decision makers.
    "pane.querySelector('[data-field=\"company-name\"]').textContent = companyName",
    "item.querySelector('[data-field=\"person-name\"]').textContent = person.name",
    "item.querySelector('[data-field=\"person-title\"]').textContent = person.title",
    "item.querySelector('[data-field=\"profile-link\"]').href = safeUrl(",
    # Person panel, including the previously missed numeric-looking fields.
    "avatar.src = safeUrl(",
    "box.querySelector('[data-field=\"person-name\"]').textContent = p.name",
    "box.querySelector('[data-field=\"person-title\"]').textContent = p.title",
    "box.querySelector('[data-field=\"department\"]').textContent = p.dept",
    "box.querySelector('[data-field=\"years-at-company\"]').textContent",
    "box.querySelector('[data-field=\"title-level\"]').textContent = p.title_level",
    "box.querySelector('[data-field=\"connection-count\"]').textContent",
    "box.querySelector('[data-field=\"profile-link\"]').href = safeUrl(",
    # Graph tooltip, including followers.
    "graphInfoContent.querySelector('[data-field=\"company-name\"]').textContent = node.name",
    "graphInfoContent.querySelector('[data-field=\"company-industry\"]').textContent = node.industry",
    "graphInfoContent.querySelector('[data-field=\"company-followers\"]').textContent",
    "graphInfoContent.querySelector('[data-field=\"company-about\"]').textContent = node.about",
]


@pytest.mark.parametrize("snippet", DOM_ASSIGNMENTS)
def test_untrusted_values_are_assigned_through_dom_properties(snippet):
    assert snippet in _html()


def test_network_tooltips_use_text_elements():
    html = _html()
    assert "title: textElement(`${n.name}" in html
    assert "title: textElement(`${p.name}" in html


def test_chat_html_is_sanitized_and_streaming_does_not_reparse_html():
    html = _html()
    assert re.search(r'<script src="[^"]*dompurify[^"]*"', html, re.I)
    assert "contentEl.innerHTML = DOMPurify.sanitize(marked.parse(text))" in html
    assert "appendTextWithBreaks(el.lastChild, text)" in html
    assert ".innerHTML +=" not in html
    assert "escapeHtml" not in html
