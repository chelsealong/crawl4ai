import threading

import pytest

pypdf = pytest.importorskip("pypdf")

from crawl4ai.processors.pdf.processor import NaivePDFProcessorStrategy

N_PAGES = 4


class _FakePage:
    """Every page holds an author-like line; the barrier keeps all workers
    inside process_batch at once, so shared per-page state would be clobbered."""

    def __init__(self, barrier):
        self.barrier = barrier

    def extract_text(self, visitor_text=None):
        self.barrier.wait(timeout=10)
        visitor_text("Alice Smith", None, [0, 0, 0, 0, 0, 0], None, 12)

    def get(self, key, default=None):
        return default

    def __contains__(self, key):
        return False


def test_process_batch_page_numbers_under_concurrency(tmp_path, monkeypatch):
    barrier = threading.Barrier(N_PAGES)

    class _FakeReader:
        def __init__(self, stream):
            self.pages = [_FakePage(barrier) for _ in range(N_PAGES)]

    monkeypatch.setattr(pypdf, "PdfReader", _FakeReader)

    pdf_path = tmp_path / "fake.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    strategy = NaivePDFProcessorStrategy(extract_images=False, batch_size=N_PAGES)
    strategy._extract_metadata = lambda path, reader: pypdf_metadata()
    strategy._extract_links = lambda page: []

    result = strategy.process_batch(pdf_path)

    assert [p.page_number for p in result.pages] == list(range(1, N_PAGES + 1))
    # Author formatting only applies on page 1
    assert "**Alice Smith**" in result.pages[0].markdown
    for page in result.pages[1:]:
        assert "**Alice Smith**" not in page.markdown
        assert "Alice Smith" in page.markdown


def pypdf_metadata():
    from crawl4ai.processors.pdf.processor import PDFMetadata
    return PDFMetadata()
