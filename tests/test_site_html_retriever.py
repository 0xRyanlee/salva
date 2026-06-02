from retrieval.sources.site_html import SiteHTMLRetriever
from salva_core.schemas import RetrievalPolicy


def test_site_html_retriever_uses_configured_domains(monkeypatch) -> None:
    policy = RetrievalPolicy(site_domains=["example.com"])
    retriever = SiteHTMLRetriever(policy=policy)

    monkeypatch.setattr(
        retriever,
        "_search_ddg",
        lambda query, n: [{"title": "Example", "url": "https://example.com/page", "snippet": "snippet"}],
    )
    monkeypatch.setattr(
        retriever,
        "_fetch_url",
        lambda url: "<html><head><title>Example Title</title></head><body><p>hello</p></body></html>",
    )

    results = retriever.search("toy expo", n=5)
    assert len(results) == 1
    assert results[0]["engine"] == "site_html"
    assert results[0]["retrieval_instance"] == "example.com"
    assert retriever.last_attempts[0].succeeded is True


def test_site_html_retriever_uses_env_domains(monkeypatch) -> None:
    monkeypatch.setenv("SITE_HTML_DOMAINS", "example.org")
    policy = RetrievalPolicy()
    retriever = SiteHTMLRetriever(policy=policy)

    monkeypatch.setattr(
        retriever,
        "_search_ddg",
        lambda query, n: [{"title": "Example", "url": "https://example.org/page", "snippet": "snippet"}],
    )
    monkeypatch.setattr(
        retriever,
        "_fetch_url",
        lambda url: "<html><head><title>Example Title</title></head><body><p>hello</p></body></html>",
    )

    results = retriever.search("event", n=5)
    assert len(results) == 1
    assert results[0]["retrieval_instance"] == "example.org"
