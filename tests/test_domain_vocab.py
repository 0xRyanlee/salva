"""Tests for the DomainVocab registry and injection system (A1)."""
from core.domain_vocab import DomainVocab, get_vocab, list_domains, register_domain
from core.keyword_graph import KeywordGraph
from core.types import Intent


# ---------------------------------------------------------------------------
# Registry basics
# ---------------------------------------------------------------------------

def test_all_builtin_domains_present() -> None:
    domains = set(list_domains())
    expected = {"events", "bd_leads", "companies", "market_intel", "partnerships", "general"}
    assert expected.issubset(domains)


def test_unknown_domain_falls_back_to_general_not_bd_leads() -> None:
    unknown = get_vocab("nonexistent_domain")
    general  = get_vocab("general")
    bd_leads = get_vocab("bd_leads")
    assert unknown.source_hints == general.source_hints
    assert unknown.source_hints != bd_leads.source_hints


def test_all_builtin_domains_have_source_hints() -> None:
    for domain in list_domains():
        vocab = get_vocab(domain)
        assert vocab.source_hints, f"{domain} must have at least one source_hint"


def test_all_builtin_domains_have_signal_terms() -> None:
    for domain in ["events", "bd_leads", "companies", "market_intel", "partnerships"]:
        vocab = get_vocab(domain)
        assert vocab.signal_terms, f"{domain} must have signal_terms"


def test_general_has_no_industry_assumptions() -> None:
    general = get_vocab("general")
    # General vocab intentionally has no industry-specific synonym groups
    assert len(general.synonym_groups) == 0


# ---------------------------------------------------------------------------
# DomainVocab.merge
# ---------------------------------------------------------------------------

def test_merge_extends_signal_terms() -> None:
    base  = get_vocab("bd_leads")
    hints = DomainVocab(signal_terms=["custom_signal"])
    merged = base.merge(hints)
    assert "custom_signal" in merged.signal_terms
    assert "B2B" in merged.signal_terms  # base preserved


def test_merge_extends_source_hints() -> None:
    base  = get_vocab("events")
    hints = DomainVocab(source_hints=["custom-events.io"])
    merged = base.merge(hints)
    assert "custom-events.io" in merged.source_hints
    assert "lu.ma" in merged.source_hints  # base preserved


def test_merge_extends_synonym_groups() -> None:
    base  = get_vocab("companies")
    hints = DomainVocab(synonym_groups={"llm": ["large language model", "AI model"]})
    merged = base.merge(hints)
    assert "llm" in merged.synonym_groups
    assert "startup" in merged.synonym_groups  # base preserved


def test_merge_deduplicates() -> None:
    base  = get_vocab("bd_leads")
    # Add a term that already exists in base
    hints = DomainVocab(signal_terms=["B2B"])
    merged = base.merge(hints)
    assert merged.signal_terms.count("B2B") == 1


def test_merge_does_not_mutate_base() -> None:
    base   = get_vocab("bd_leads")
    before = list(base.signal_terms)
    hints  = DomainVocab(signal_terms=["injection"])
    base.merge(hints)
    assert base.signal_terms == before


# ---------------------------------------------------------------------------
# register_domain (runtime extension)
# ---------------------------------------------------------------------------

def test_register_custom_domain() -> None:
    custom = DomainVocab(
        signal_terms=["clause", "statute"],
        source_hints=["lex.europa.eu"],
    )
    register_domain("legal", custom)
    assert get_vocab("legal").signal_terms == ["clause", "statute"]


# ---------------------------------------------------------------------------
# KeywordGraph boots from DomainVocab
# ---------------------------------------------------------------------------

def test_graph_boots_with_unknown_domain_using_general_vocab() -> None:
    intent = Intent(domain="unknown_niche", primary_terms=["niche term"])
    graph  = KeywordGraph(intent=intent)
    # Primary terms always bootstrapped
    assert "niche term" in graph.nodes
    # General vocab: no synonym expansion (empty synonym_groups)
    assert sum(1 for n in graph.nodes.values() if n.node_type == "synonym") == 0


def test_graph_boots_with_companies_domain() -> None:
    intent = Intent(domain="companies", primary_terms=["saas platform"], region="Berlin")
    graph  = KeywordGraph(intent=intent)
    # Should have signal nodes from companies vocab
    signal_nodes = [n for n in graph.nodes.values() if n.node_type == "signal"]
    assert len(signal_nodes) > 0


def test_graph_accepts_injected_vocab() -> None:
    custom = DomainVocab(
        synonym_groups={"legaltech": ["legal software", "law tech"]},
        signal_terms=["compliance", "regulatory"],
        source_hints=["law360.com"],
    )
    intent = Intent(domain="legaltech", primary_terms=["legaltech"])
    graph  = KeywordGraph(intent=intent, vocab=custom)
    # Synonyms expanded since "legaltech" is in synonym_groups and in nodes
    synonym_nodes = [n for n in graph.nodes.values() if n.node_type == "synonym"]
    assert len(synonym_nodes) == 2  # "legal software" and "law tech"


def test_graph_injected_vocab_overrides_registry() -> None:
    # Even if bd_leads is in registry, explicit vocab takes precedence
    custom = DomainVocab(source_hints=["only-this.com"])
    intent = Intent(domain="bd_leads", primary_terms=["reseller"])
    graph  = KeywordGraph(intent=intent, vocab=custom)
    # The graph's vocab should be the custom one
    assert graph.vocab.source_hints == ["only-this.com"]


# ---------------------------------------------------------------------------
# seed_from_memory (A3)
# ---------------------------------------------------------------------------

def test_seed_from_memory_injects_new_nodes() -> None:
    intent = Intent(domain="companies", primary_terms=["ai startup"])
    graph  = KeywordGraph(intent=intent)
    before = set(graph.nodes.keys())

    def reader(domain: str, top_k: int) -> list[dict]:
        return [{"source_nodes": ["funding round", "series a"], "success_score": 0.9}]

    injected = graph.seed_from_memory(reader)
    assert injected == 2
    assert "funding round" in graph.nodes
    assert graph.nodes["funding round"].node_type == "memory"
    assert graph.nodes["funding round"].weight == 0.5


def test_seed_from_memory_skips_existing_nodes() -> None:
    intent = Intent(domain="companies", primary_terms=["ai startup"])
    graph  = KeywordGraph(intent=intent)

    # "ai startup" is already a primary node
    def reader(domain: str, top_k: int) -> list[dict]:
        return [{"source_nodes": ["ai startup", "new node"], "success_score": 0.8}]

    injected = graph.seed_from_memory(reader)
    assert injected == 1  # only "new node" is new
    # primary node weight must not be overwritten
    assert graph.nodes["ai startup"].node_type == "primary"
    assert graph.nodes["ai startup"].weight == 1.0


def test_seed_from_memory_tolerates_reader_error() -> None:
    intent = Intent(domain="companies", primary_terms=["ai startup"])
    graph  = KeywordGraph(intent=intent)
    before = set(graph.nodes.keys())

    def failing_reader(domain: str, top_k: int) -> list[dict]:
        raise RuntimeError("DB unavailable")

    injected = graph.seed_from_memory(failing_reader)
    assert injected == 0
    assert set(graph.nodes.keys()) == before  # unchanged


def test_seed_from_memory_empty_records() -> None:
    intent = Intent(domain="general", primary_terms=["any topic"])
    graph  = KeywordGraph(intent=intent)

    injected = graph.seed_from_memory(lambda d, k: [])
    assert injected == 0
