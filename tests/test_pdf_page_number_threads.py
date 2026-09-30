import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

pytest.importorskip("pypdf")

from crawl4ai.processors.pdf.processor import NaivePDFProcessorStrategy


class _SlowPage:
    """Fake page; the barrier forces every worker past its start before any finishes."""

    def __init__(self, barrier):
        self.barrier = barrier

    def extract_text(self, visitor_text=None):
        self.barrier.wait(timeout=10)
        visitor_text("text", None, [0, 0, 0, 0, 0, 0], None, 12)

    def get(self, key, default=None):
        return default

    def __contains__(self, key):
        return False


def test_page_number_is_not_shared_between_threads():
    n = 4
    barrier = threading.Barrier(n)
    strategy = NaivePDFProcessorStrategy(extract_images=False)
    strategy._extract_links = lambda page: []

    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [
            pool.submit(strategy._process_page, _SlowPage(barrier), None, i + 1)
            for i in range(n)
        ]
        pages = [f.result() for f in futures]

    assert [p.page_number for p in pages] == [1, 2, 3, 4]

