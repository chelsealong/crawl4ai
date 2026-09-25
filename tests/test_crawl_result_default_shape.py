"""
Test for issue #2286: a failed CrawlResult (built without passing media/links,
e.g. robots.txt refusal, "All proxies failed", exception path) must expose the
same media/links keys as a successful one, instead of `{}`.
"""

from crawl4ai.models import CrawlResult


def test_default_media_has_standard_keys():
    result = CrawlResult(
        url="https://example.com/private",
        html="",
        success=False,
        status_code=403,
        error_message="Access denied by robots.txt",
    )
    assert result.media == {"images": [], "videos": [], "audios": []}


def test_default_links_has_standard_keys():
    result = CrawlResult(
        url="https://example.com/private",
        html="",
        success=False,
        status_code=403,
        error_message="Access denied by robots.txt",
    )
    assert result.links == {"internal": [], "external": []}
    result.links["internal"]  # must not raise KeyError


def test_default_media_and_links_are_independent_per_instance():
    a = CrawlResult(url="https://example.com/a", html="", success=True)
    b = CrawlResult(url="https://example.com/b", html="", success=True)
    a.media["images"].append({"src": "x"})
    assert b.media["images"] == []
