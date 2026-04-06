"""
Unit tests for EarningsSense analysis modules.

Run with:
    pytest tests/ -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.linguistics import extract, LinguisticFeatures
from src.analysis.signals import compute_scores, backtest, Scores


# ── Fixtures ──────────────────────────────────────────────────────────────────

CONFIDENT_TEXT = """
We will achieve record revenue this quarter. Our team is absolutely committed
to delivering exceptional results. We are well-positioned and confident in our
ability to outperform market expectations. We will expand our market share
significantly and our pipeline is stronger than ever. We are decisively on track
to exceed our targets and our execution has been outstanding.
"""

HEDGING_TEXT = """
We believe there may be some potential uncertainty in certain markets that could
possibly impact our results. We expect that various macroeconomic factors might
present challenges. Subject to market conditions, we anticipate that we could
potentially see some improvement, though this remains dependent on several
uncertain external factors. We hope to possibly achieve approximately our targets.
"""

NEUTRAL_TEXT = """
Revenue for the quarter was $10 billion. Operating expenses were $3 billion.
Headcount increased by 500 employees. We opened 12 new facilities.
The board approved a quarterly dividend of $0.25 per share.
"""


# ── Linguistics tests ─────────────────────────────────────────────────────────

class TestLinguistics:
    def test_returns_dataclass(self):
        result = extract(CONFIDENT_TEXT)
        assert isinstance(result, LinguisticFeatures)

    def test_confident_text_low_hedge_density(self):
        result = extract(CONFIDENT_TEXT)
        assert result.hedge_density < 2.0, (
            f"Confident text should have low hedge density, got {result.hedge_density}"
        )

    def test_confident_text_high_certainty_ratio(self):
        result = extract(CONFIDENT_TEXT)
        assert result.certainty_ratio > 1.5, (
            f"Confident text should have high certainty ratio, got {result.certainty_ratio}"
        )

    def test_hedging_text_high_hedge_density(self):
        result = extract(HEDGING_TEXT)
        assert result.hedge_density > 2.0, (
            f"Hedging text should have high hedge density, got {result.hedge_density}"
        )

    def test_hedging_text_low_certainty_ratio(self):
        result = extract(HEDGING_TEXT)
        assert result.certainty_ratio < 1.0, (
            f"Hedging text should have low certainty ratio, got {result.certainty_ratio}"
        )

    def test_empty_text_returns_defaults(self):
        result = extract("")
        assert result.word_count == 0
        assert result.hedge_density == 0.0

    def test_word_count_positive(self):
        result = extract(CONFIDENT_TEXT)
        assert result.word_count > 0

    def test_passive_voice_ratio_bounded(self):
        result = extract(CONFIDENT_TEXT)
        assert 0.0 <= result.passive_voice_ratio <= 1.0

    def test_confident_vs_hedging_hedge_density(self):
        confident = extract(CONFIDENT_TEXT)
        hedging   = extract(HEDGING_TEXT)
        assert confident.hedge_density < hedging.hedge_density, (
            "Confident text should have lower hedge density than hedging text"
        )

    def test_confident_vs_hedging_certainty(self):
        confident = extract(CONFIDENT_TEXT)
        hedging   = extract(HEDGING_TEXT)
        assert confident.certainty_ratio > hedging.certainty_ratio, (
            "Confident text should have higher certainty ratio"
        )


# ── Signals tests ─────────────────────────────────────────────────────────────

class MockSentiment:
    def __init__(self, positive, negative, neutral):
        self.positive = positive
        self.negative = negative
        self.neutral  = neutral

class MockLinguistics:
    def __init__(self, hedge, certainty, passive, vague):
        self.hedge_density        = hedge
        self.certainty_ratio      = certainty
        self.passive_voice_ratio  = passive
        self.vague_language_score = vague


class TestSignals:
    def test_returns_scores_dataclass(self):
        sent = MockSentiment(0.7, 0.1, 0.2)
        ling = MockLinguistics(1.0, 3.0, 0.1, 0.5)
        result = compute_scores(sent, ling)
        assert isinstance(result, Scores)

    def test_mci_bounded_0_to_100(self):
        for pos, neg, neu in [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.33, 0.33, 0.34)]:
            sent = MockSentiment(pos, neg, neu)
            ling = MockLinguistics(0.5, 2.0, 0.1, 0.5)
            result = compute_scores(sent, ling)
            assert 0 <= result.management_confidence_index <= 100

    def test_drs_bounded_0_to_100(self):
        sent = MockSentiment(0.1, 0.8, 0.1)
        ling = MockLinguistics(4.5, 0.2, 0.45, 2.8)
        result = compute_scores(sent, ling)
        assert 0 <= result.deception_risk_score <= 100

    def test_confident_profile_high_mci(self):
        sent = MockSentiment(0.8, 0.05, 0.15)
        ling = MockLinguistics(hedge=0.5, certainty=4.0, passive=0.05, vague=0.3)
        result = compute_scores(sent, ling)
        assert result.management_confidence_index > 70, (
            f"Highly confident profile should yield MCI > 70, got {result.management_confidence_index}"
        )

    def test_hedging_profile_high_drs(self):
        sent = MockSentiment(0.1, 0.7, 0.2)
        ling = MockLinguistics(hedge=4.5, certainty=0.2, passive=0.4, vague=2.5)
        result = compute_scores(sent, ling)
        assert result.deception_risk_score > 60, (
            f"Hedging profile should yield DRS > 60, got {result.deception_risk_score}"
        )

    def test_mci_drs_rough_inverse_relationship(self):
        # High confidence → low risk
        sent_conf = MockSentiment(0.8, 0.05, 0.15)
        ling_conf = MockLinguistics(0.5, 4.0, 0.05, 0.3)
        conf_result = compute_scores(sent_conf, ling_conf)

        # High hedging → high risk
        sent_hedg = MockSentiment(0.1, 0.7, 0.2)
        ling_hedg = MockLinguistics(4.5, 0.2, 0.4, 2.5)
        hedg_result = compute_scores(sent_hedg, ling_hedg)

        assert conf_result.management_confidence_index > hedg_result.management_confidence_index
        assert conf_result.deception_risk_score < hedg_result.deception_risk_score


class TestBacktest:
    MOCK_SAMPLES = [
        {"scores": {"management_confidence_index": 87.2}, "price_impact": {"next_day_return":  0.054}, "ticker": "NVDA", "quarter": "Q3 FY2025"},
        {"scores": {"management_confidence_index": 78.1}, "price_impact": {"next_day_return":  0.020}, "ticker": "META", "quarter": "Q3 2024"},
        {"scores": {"management_confidence_index": 73.8}, "price_impact": {"next_day_return":  0.062}, "ticker": "AMZN", "quarter": "Q3 2024"},
        {"scores": {"management_confidence_index": 71.4}, "price_impact": {"next_day_return":  0.029}, "ticker": "GOOGL","quarter": "Q3 2024"},
        {"scores": {"management_confidence_index": 69.3}, "price_impact": {"next_day_return":  0.005}, "ticker": "AAPL", "quarter": "Q4 FY2024"},
        {"scores": {"management_confidence_index": 74.2}, "price_impact": {"next_day_return": -0.036}, "ticker": "MSFT", "quarter": "Q1 FY2025"},
        {"scores": {"management_confidence_index": 74.8}, "price_impact": {"next_day_return":  0.219}, "ticker": "TSLA", "quarter": "Q3 2024"},
        {"scores": {"management_confidence_index": 28.7}, "price_impact": {"next_day_return": -0.092}, "ticker": "INTC", "quarter": "Q3 2024"},
    ]

    def test_backtest_returns_result(self):
        result = backtest(self.MOCK_SAMPLES)
        assert hasattr(result, "pearson_r")
        assert hasattr(result, "p_value")
        assert hasattr(result, "n_observations")

    def test_pearson_r_bounded(self):
        result = backtest(self.MOCK_SAMPLES)
        assert -1.0 <= result.pearson_r <= 1.0

    def test_p_value_bounded(self):
        result = backtest(self.MOCK_SAMPLES)
        assert 0.0 <= result.p_value <= 1.0

    def test_observation_count(self):
        result = backtest(self.MOCK_SAMPLES)
        assert result.n_observations == len(self.MOCK_SAMPLES)

    def test_positive_correlation_direction(self):
        # Our sample data should show a positive (MCI predicts returns) correlation
        result = backtest(self.MOCK_SAMPLES)
        assert result.pearson_r > 0, (
            "Sample data should show positive correlation between MCI and returns"
        )

    def test_insufficient_data(self):
        result = backtest([self.MOCK_SAMPLES[0]])
        assert result.pearson_r == 0.0
        assert result.p_value == 1.0

    def test_interpretation_is_string(self):
        result = backtest(self.MOCK_SAMPLES)
        assert isinstance(result.interpretation, str)
        assert len(result.interpretation) > 0
