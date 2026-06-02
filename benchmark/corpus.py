"""Synthetic fixture corpus for the compounding-memory benchmark.

The corpus is deterministic and vocabulary-aligned with the built-in `companies`
DomainVocab so that the KeywordGraph's expanded queries can actually match docs.

Relevant (gold) docs split into two tiers:
  - tier "primary": reachable from primary/region terms in early queries.
  - tier "signal":  reachable mainly via specific signal terms (founded, series B,
    acquired, CTO, ...) that start at low weight and only get prioritised once
    memory seeding re-surfaces the productive ones.

This structure leaves headroom under a small query budget: a blind first run
reaches the primary tier; later memory-seeded runs should reach more of the
signal tier within the same budget.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Doc:
    url: str
    title: str
    snippet: str
    relevant: bool


# Invented company names — neutral synthetic fixtures, not real entities.
CORPUS: list[Doc] = [
    # ── tier primary: germany / software / enterprise / berlin / munich ──
    Doc("https://ex.test/nordwind", "Nordwind Systems",
        "Berlin enterprise software company building logistics platforms in Germany.", True),
    Doc("https://ex.test/helioscale", "Helioscale GmbH",
        "Munich based enterprise software corporation serving multinational clients.", True),
    Doc("https://ex.test/aurelis", "Aurelis Software",
        "Germany enterprise software vendor headquartered in Berlin.", True),
    Doc("https://ex.test/kettentech", "Kettentech AG",
        "Large-cap enterprise software corporation in Munich, Germany.", True),
    Doc("https://ex.test/blauwerk", "Blauwerk Digital",
        "Berlin software company, multinational enterprise customers across Europe.", True),

    # ── tier signal: reachable mainly via signal terms ──
    Doc("https://ex.test/farben", "Farben Labs",
        "Series B funding round led by venture-backed investors; CTO previously at a large-cap firm.", True),
    Doc("https://ex.test/vektor", "Vektor Industries",
        "Founded 2014, headquarters relocated after series A investment; 200 employees.", True),
    Doc("https://ex.test/granit", "Granit Holdings",
        "Recently acquired in a merger; CEO announced new leadership team and headcount growth.", True),
    Doc("https://ex.test/silberpfad", "Silberpfad",
        "Revenue doubled post IPO; founded by ex-CTO, headquarters in the Bay Area.", True),
    Doc("https://ex.test/morgenstern", "Morgenstern Capital",
        "Early-stage seed-stage startup; series A raise closed with venture capital.", True),
    Doc("https://ex.test/eisenhart", "Eisenhart Group",
        "Multinational corporation, Fortune 500 supplier; CEO and CTO lead a large team.", True),
    Doc("https://ex.test/talwind", "Talwind Ventures",
        "Investment firm tracking funding rounds, series A and series B raises.", True),

    # ── noise: contain noise_terms and decoy overlap ──
    Doc("https://ex.test/n1", "Best software jobs",
        "Glassdoor salary review for software roles; reddit thread on enterprise pay in Germany.", False),
    Doc("https://ex.test/n2", "Munich travel guide",
        "Things to do in Munich and Berlin; restaurant review and city tips.", False),
    Doc("https://ex.test/n3", "Job posting board",
        "Software engineer job posting, salary range, glassdoor company review.", False),
    Doc("https://ex.test/n4", "Reddit discussion",
        "Reddit thread about startup culture and venture funding opinions.", False),
    Doc("https://ex.test/n5", "Enterprise software review",
        "Independent review and ratings of enterprise software products.", False),
    Doc("https://ex.test/n6", "Germany news digest",
        "Daily news from Berlin and Munich, unrelated to company research.", False),
    Doc("https://ex.test/n7", "Software tutorial",
        "Learn enterprise software development with this beginner tutorial.", False),
    Doc("https://ex.test/n8", "Salary report",
        "Annual salary report for CTO and CEO roles, glassdoor data.", False),
]

GOLD_URLS: set[str] = {d.url for d in CORPUS if d.relevant}
