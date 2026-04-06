"""
FinBERT-based sentiment analysis for financial text.

ProsusAI/finbert is a BERT model fine-tuned on ~10,000 financial news sentences.
It outputs positive / negative / neutral scores per sentence chunk.

The model is ~440MB and is downloaded on first run from HuggingFace Hub.
Subsequent runs use the local cache (~/.cache/huggingface/).

Reference:
  Araci, D. (2019). FinBERT: Financial Sentiment Analysis with Pre-trained
  Language Models. arXiv:1908.10063.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Lazy-loaded pipeline — avoids importing torch at module level
_pipeline = None


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class SentimentResult:
    positive: float       # avg positive score across chunks [0, 1]
    negative: float       # avg negative score across chunks [0, 1]
    neutral: float        # avg neutral score across chunks  [0, 1]
    sentence_count: int
    chunk_count: int


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_pipeline():
    """Lazy-load the FinBERT pipeline (downloads model on first call)."""
    global _pipeline
    if _pipeline is None:
        from transformers import pipeline as hf_pipeline
        _pipeline = hf_pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            return_all_scores=True,
            device=-1,          # CPU; set device=0 for GPU
            truncation=True,
        )
    return _pipeline


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _chunk_text(text: str, max_words: int = 400) -> list[str]:
    """
    Split text into sentence-boundary-respecting chunks of ≤ max_words.
    FinBERT has a 512-token limit; 400 words ≈ 500 tokens (safe margin).
    """
    sentences = _SENTENCE_SPLIT.split(text.strip())
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        word_len = len(sentence.split())
        if current_len + word_len > max_words and current:
            chunks.append(" ".join(current))
            current = [sentence]
            current_len = word_len
        else:
            current.append(sentence)
            current_len += word_len

    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if c.strip()]


# ── Public API ────────────────────────────────────────────────────────────────

def analyze(text: str) -> SentimentResult:
    """
    Run FinBERT on financial text and return aggregated sentiment scores.

    The text is split into ≤400-word chunks at sentence boundaries.
    Scores are averaged across all chunks (macro-average).

    Args:
        text: Raw transcript or filing text.

    Returns:
        SentimentResult with positive, negative, neutral scores summing to ~1.
    """
    if not text or not text.strip():
        return SentimentResult(0.33, 0.33, 0.34, 0, 0)

    pipe = _get_pipeline()
    chunks = _chunk_text(text)
    sentence_count = len(_SENTENCE_SPLIT.split(text.strip()))

    pos_scores: list[float] = []
    neg_scores: list[float] = []
    neu_scores: list[float] = []

    for chunk in chunks:
        if not chunk.strip():
            continue
        results = pipe(chunk)[0]
        score_map = {r["label"]: r["score"] for r in results}
        pos_scores.append(score_map.get("positive", 0.0))
        neg_scores.append(score_map.get("negative", 0.0))
        neu_scores.append(score_map.get("neutral", 0.0))

    if not pos_scores:
        return SentimentResult(0.33, 0.33, 0.34, sentence_count, 0)

    return SentimentResult(
        positive=round(sum(pos_scores) / len(pos_scores), 4),
        negative=round(sum(neg_scores) / len(neg_scores), 4),
        neutral=round(sum(neu_scores) / len(neu_scores), 4),
        sentence_count=sentence_count,
        chunk_count=len(chunks),
    )
