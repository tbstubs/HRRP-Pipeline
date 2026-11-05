"""Tests for the download layer.

These never touch the network. The HTTP call is replaced so the guard clauses
and the partial-file handling can be tested deterministically — a test that
depends on CMS being up is a test that fails for reasons unrelated to the code.
"""

import pytest

from src.ingestion import downloader


class FakeResponse:
    """Minimal stand-in for requests.Response, enough for download()."""

    def __init__(self, chunks=(b"col\n", b"1\n"), content_type="text/csv", status_ok=True):
        self._chunks = chunks
        self.headers = {"Content-Type": content_type}
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise RuntimeError("simulated HTTP error")

    def iter_content(self, chunk_size=None):
        return iter(self._chunks)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def no_network(monkeypatch):
    """Patch out URL resolution and the streaming GET."""

    def _install(response):
        monkeypatch.setattr(downloader, "resolve_download_url", lambda _id: "https://example/x.csv")
        monkeypatch.setattr(downloader.requests, "get", lambda *a, **kw: response)

    return _install


class TestGuardClauses:
    def test_unknown_dataset_name_raises(self):
        with pytest.raises(KeyError, match="unknown dataset"):
            downloader.download("not_a_dataset")

    def test_html_error_page_is_rejected(self, tmp_path, no_network):
        """A 200 response is not proof you got a CSV."""
        no_network(FakeResponse(content_type="text/html"))
        with pytest.raises(ValueError, match="expected a CSV"):
            downloader.download("hospitals", dest_dir=tmp_path)

    def test_empty_download_is_rejected(self, tmp_path, no_network):
        no_network(FakeResponse(chunks=()))
        with pytest.raises(ValueError, match="empty"):
            downloader.download("hospitals", dest_dir=tmp_path)


class TestSuccessPath:
    def test_writes_file_named_for_the_internal_key(self, tmp_path, no_network):
        no_network(FakeResponse())
        path = downloader.download("hospitals", dest_dir=tmp_path)
        assert path.name == "hospitals.csv"
        assert path.read_bytes() == b"col\n1\n"

    def test_creates_missing_directories(self, tmp_path, no_network):
        no_network(FakeResponse())
        nested = tmp_path / "a" / "b"
        downloader.download("hospitals", dest_dir=nested)
        assert nested.is_dir()

    def test_no_partial_file_is_left_behind(self, tmp_path, no_network):
        no_network(FakeResponse())
        downloader.download("hospitals", dest_dir=tmp_path)
        assert list(tmp_path.glob("*.partial")) == []

    def test_failed_download_leaves_no_file_at_the_real_path(self, tmp_path, no_network):
        """The point of the temp-then-rename: no truncated file looks complete."""
        no_network(FakeResponse(chunks=()))
        with pytest.raises(ValueError):
            downloader.download("hospitals", dest_dir=tmp_path)
        assert not (tmp_path / "hospitals.csv").exists()


class TestDownloadAll:
    def test_one_failure_does_not_stop_the_others(self, tmp_path, no_network, caplog):
        no_network(FakeResponse())
        results = downloader.download_all(["hospitals", "not_a_dataset"], dest_dir=tmp_path)
        assert list(results) == ["hospitals"]
        assert "not_a_dataset" in caplog.text

    def test_defaults_to_every_configured_dataset(self, tmp_path, no_network):
        no_network(FakeResponse())
        results = downloader.download_all(dest_dir=tmp_path)
        assert set(results) == set(downloader.CMS_DATASETS)
