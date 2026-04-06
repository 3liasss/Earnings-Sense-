"""
Linguistic feature extraction for management language analysis.

Identifies hedging language, certainty signals, passive voice patterns,
and vague terminology — the same signals quantitative hedge funds pay
alternative data vendors millions to extract from earnings transcripts.

Academic basis:
  - Loughran & McDonald (2011), "When Is a Liability Not a Liability?
    Textual Analysis, Dictionaries, and 10-Ks", Journal of Finance
  - Li (2010), "The Information Content of Forward-Looking Statements
    in Corporate Filings", Journal of Accounting Research
  - Rogers, Van Buskirk & Zechman (2011), "Modifying the Tone of
    Conference Calls"
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ── Word lists ────────────────────────────────────────────────────────────────

HEDGE_PHRASES = [
    "we believe", "we expect", "we anticipate", "we hope", "we think",
    "we feel", "we consider", "approximately", "subject to", "may",
    "might", "could", "would", "pending", "potentially", "possible",
    "possibly", "perhaps", "if and when", "assuming", "contingent",
    "dependent on", "to the extent", "challenging", "headwinds",
    "uncertain", "uncertainty", "remains to be seen", "going forward",
    "we aim", "we intend", "we plan", "we target", "we project",
    "we estimate", "roughly", "broadly", "largely", "in the range of",
    "approximately", "around", "about",
]

CERTAINTY_PHRASES = [
    "will", "confident", "committed", "delivering", "record",
    "exceptional", "outstanding", "accelerating", "dominant",
    "leading", "best-in-class", "well-positioned", "strong demand",
    "significantly exceed", "outperform", "breakthrough", "decisive",
    "unequivocal", "certain", "clearly", "absolutely", "definitely",
]

VAGUE_TERMS = [
    "various", "significant", "some", "certain", "ongoing", "several",
    "numerous", "many", "few", "multiple", "substantial", "material",
    "generally", "broadly", "largely", "mostly", "primarily", "mainly",
    "relatively", "somewhat", "reasonably", "fairly", "quite",
]

# Passive voice: auxiliary + past participle
_PASSIVE_RE = re.compile(
    r"\b(is|are|was|were|be|been|being)\s+\w+ed\b", re.IGNORECASE
)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class LinguisticFeatures:
    """Container for all extracted linguistic metrics."""
    hedge_density: float        # hedging phrases per 100 words
    certainty_ratio: float      # strong affirmatives / (hedges + 1)
    passive_voice_ratio: float  # fraction of sentences that are passive
    vague_language_score: float # vague terms per 100 words
    word_count: int


# ── Main function ─────────────────────────────────────────────────────────────

def extract(text: str) -> LinguisticFeatures:
    """
    Extract linguistic features from a management transcript or filing.

    Args:
        text: Raw text of the earnings call transcript or MD&A section.

    Returns:
        LinguisticFeatures dataclass with all computed metrics.
    """
    if not text or not text.strip():
        return LinguisticFeatures(
            hedge_density=0.0,
            certainty_ratio=1.0,
            passive_voice_ratio=0.0,
            vague_language_score=0.0,
            word_count=0,
        )

    text_lower = text.lower()
    words = text.split()
    word_count = len(words)
    sentences = _SENTENCE_RE.split(text.strip())
    sentence_count = max(len(sentences), 1)

    # Hedge density: occurrences per 100 words
    hedge_count = sum(text_lower.count(p) for p in HEDGE_PHRASES)
    hedge_density = (hedge_count / word_count) * 100

    # Certainty ratio: affirmatives relative to hedges
    certainty_count = sum(text_lower.count(p) for p in CERTAINTY_PHRASES)
    certainty_ratio = certainty_count / (hedge_count + 1)

    # Passive voice ratio
    passive_count = sum(1 for s in sentences if _PASSIVE_RE.search(s))
    passive_voice_ratio = passive_count / sentence_count

    # Vague language score: occurrences per 100 words
    vague_count = sum(text_lower.count(t) for t in VAGUE_TERMS)
    vague_language_score = (vague_count / word_count) * 100

    return LinguisticFeatures(
        hedge_density=round(hedge_density, 3),
        certainty_ratio=round(certainty_ratio, 3),
        passive_voice_ratio=round(passive_voice_ratio, 3),
        vague_language_score=round(vague_language_score, 3),
        word_count=word_count,
    )
