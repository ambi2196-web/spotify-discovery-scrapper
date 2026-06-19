"""Scrapper — multi-source review-analysis pipeline for Spotify discovery diagnosis."""

__version__ = "0.1.0"

# The six diagnostic questions the pipeline maps every theme to.
# See REQUIREMENTS.md §4. Confirm wording against the fellowship brief.
DIAGNOSTIC_QUESTIONS: dict[int, str] = {
    1: "Awareness — do users know discovery features exist?",
    2: "Trust — do users believe recommendations are for them?",
    3: "Effort — how much friction between intent and outcome?",
    4: "Relevance — too safe, too random, or stuck in a loop?",
    5: "Context — do recommendations fit the moment?",
    6: "Agency — can users steer/correct discovery?",
}
