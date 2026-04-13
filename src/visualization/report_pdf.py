"""
PDF report generator for EarningsSense analysis results.

Produces a clean, printable PDF from a full analysis result dict.
Uses reportlab - installed via requirements.txt.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Colour palette ─────────────────────────────────────────────────────────────

_DARK_BG    = colors.HexColor("#0f172a")
_SURFACE    = colors.HexColor("#1e293b")
_BORDER     = colors.HexColor("#334155")
_TEXT       = colors.HexColor("#f1f5f9")
_MUTED      = colors.HexColor("#94a3b8")
_GREEN      = colors.HexColor("#22c55e")
_RED        = colors.HexColor("#ef4444")
_ORANGE     = colors.HexColor("#f97316")
_BLUE       = colors.HexColor("#3b82f6")
_PURPLE     = colors.HexColor("#a78bfa")
_WHITE      = colors.white
_BLACK      = colors.black


def _mci_color(v: float) -> colors.Color:
    if v >= 65:
        return _GREEN
    if v >= 45:
        return _ORANGE
    return _RED


def _drs_color(v: float) -> colors.Color:
    if v >= 55:
        return _RED
    if v >= 35:
        return _ORANGE
    return _GREEN


def _ret_color(v: Optional[float]) -> colors.Color:
    if v is None:
        return _MUTED
    return _GREEN if v >= 0 else _RED


# ── Style helpers ──────────────────────────────────────────────────────────────

def _styles():
    return {
        "h1":     ParagraphStyle("h1",     fontName="Helvetica-Bold",   fontSize=20, textColor=_WHITE, spaceAfter=4),
        "h2":     ParagraphStyle("h2",     fontName="Helvetica-Bold",   fontSize=13, textColor=_WHITE, spaceBefore=10, spaceAfter=4),
        "h3":     ParagraphStyle("h3",     fontName="Helvetica-Bold",   fontSize=10, textColor=_MUTED, spaceBefore=8, spaceAfter=3),
        "body":   ParagraphStyle("body",   fontName="Helvetica",        fontSize=9,  textColor=_TEXT, leading=13),
        "small":  ParagraphStyle("small",  fontName="Helvetica",        fontSize=8,  textColor=_MUTED),
        "phrase": ParagraphStyle("phrase", fontName="Helvetica-Oblique", fontSize=8.5, textColor=_TEXT, leading=12, leftIndent=8),
        "footer": ParagraphStyle("footer", fontName="Helvetica",        fontSize=7,  textColor=_MUTED, alignment=TA_CENTER),
        "center": ParagraphStyle("center", fontName="Helvetica",        fontSize=9,  textColor=_TEXT, alignment=TA_CENTER),
    }


# ── Table helpers ──────────────────────────────────────────────────────────────

_TS_BASE = TableStyle([
    ("BACKGROUND",  (0, 0), (-1, 0),  _SURFACE),
    ("TEXTCOLOR",   (0, 0), (-1, 0),  _MUTED),
    ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
    ("FONTSIZE",    (0, 0), (-1, -1), 8),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_DARK_BG, _SURFACE]),
    ("TEXTCOLOR",   (0, 1), (-1, -1), _TEXT),
    ("GRID",        (0, 0), (-1, -1), 0.25, _BORDER),
    ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING",   (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
])


def _kpi_table(mci: float, drs: float, gs: float,
               ret: Optional[float], styles: dict) -> Table:
    """Four-column KPI table at the top of the report."""
    ret_str = f"{ret * 100:+.2f}%" if ret is not None else "-"

    header = ["MCI", "DRS", "Guidance Score", "Next-Day Return"]
    values = [f"{mci:.0f}", f"{drs:.0f}", f"{gs:.0f}", ret_str]
    labels = ["Management Confidence", "Deception Risk", "Forward confidence", "Post-filing"]

    col_w = [3.8 * cm] * 4

    data = [header, values, labels]

    ts = TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  _SURFACE),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  _MUTED),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  8),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME",     (0, 1), (-1, 1),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 1), (-1, 1),  20),
        ("TEXTCOLOR",    (0, 1), (0, 1),   _mci_color(mci)),
        ("TEXTCOLOR",    (1, 1), (1, 1),   _drs_color(drs)),
        ("TEXTCOLOR",    (2, 1), (2, 1),   _PURPLE),
        ("TEXTCOLOR",    (3, 1), (3, 1),   _ret_color(ret)),
        ("FONTSIZE",     (0, 2), (-1, 2),  7),
        ("TEXTCOLOR",    (0, 2), (-1, 2),  _MUTED),
        ("GRID",         (0, 0), (-1, -1), 0.25, _BORDER),
        ("BACKGROUND",   (0, 1), (-1, 2),  _DARK_BG),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ])

    t = Table(data, colWidths=col_w)
    t.setStyle(ts)
    return t


def _linguistics_table(ling: dict) -> Table:
    header = ["Metric", "Value", "Signal"]
    rows = [
        ("Hedge Density",       f"{ling['hedge_density']:.2f}",       "hedges per 100 words"),
        ("Certainty Ratio",     f"{ling['certainty_ratio']:.2f}",      "affirmatives / hedges"),
        ("Passive Voice",       f"{ling['passive_voice_ratio']:.1%}",  "% sentences passive"),
        ("Vague Language",      f"{ling['vague_language_score']:.2f}", "vague terms per 100 words"),
        ("Word Count",          f"{ling['word_count']:,}",             "analysed words"),
        ("Avg Sentence Length", f"{ling['avg_sentence_length']:.1f}",  "words per sentence"),
    ]
    data = [header] + list(rows)
    col_w = [5.5 * cm, 3 * cm, 8 * cm]
    t = Table(data, colWidths=col_w)
    t.setStyle(_TS_BASE)
    return t


def _sentiment_table(sent: dict) -> Table:
    header = ["Positive", "Negative", "Neutral", "Sentences", "Chunks"]
    row = [
        f"{sent['positive']:.1%}",
        f"{sent['negative']:.1%}",
        f"{sent['neutral']:.1%}",
        str(sent["sentence_count"]),
        str(sent["chunk_count"]),
    ]
    data = [header, row]
    col_w = [3.2 * cm] * 5
    ts = TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  _SURFACE),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  _MUTED),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 8),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR",    (0, 1), (0, 1),   _GREEN),
        ("TEXTCOLOR",    (1, 1), (1, 1),   _RED),
        ("TEXTCOLOR",    (0, 1), (-1, 1),  _TEXT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_DARK_BG]),
        ("GRID",         (0, 0), (-1, -1), 0.25, _BORDER),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ])
    t = Table(data, colWidths=col_w)
    t.setStyle(ts)
    return t


def _qa_table(main_mci: float, main_drs: float,
              qa_mci: float, qa_drs: float) -> Table:
    mci_delta = qa_mci - main_mci
    drs_delta = qa_drs - main_drs
    header = ["Section", "MCI", "DRS"]
    rows = [
        ("Prepared Remarks", f"{main_mci:.0f}", f"{main_drs:.0f}"),
        ("Q&A Session",
         f"{qa_mci:.0f}  ({mci_delta:+.1f})",
         f"{qa_drs:.0f}  ({drs_delta:+.1f})"),
    ]
    data = [header] + list(rows)
    col_w = [6 * cm, 4 * cm, 4 * cm]
    t = Table(data, colWidths=col_w)
    t.setStyle(_TS_BASE)
    return t


def _eps_table(surprises: list[dict]) -> Table:
    header = ["Date", "Actual EPS", "Estimate EPS", "Surprise %"]
    rows = []
    for s in surprises[:6]:
        rows.append((
            s.get("date", ""),
            f"${s['actual_eps']:.3f}",
            f"${s['estimated_eps']:.3f}",
            f"{s['surprise_pct']:+.2f}%",
        ))
    data = [header] + rows
    col_w = [4 * cm, 4 * cm, 4 * cm, 4 * cm]
    t = Table(data, colWidths=col_w)
    t.setStyle(_TS_BASE)
    return t


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_pdf(result: dict) -> bytes:
    """
    Build a PDF report from a full analysis result dict.

    Parameters
    ----------
    result : dict
        The complete result dict produced by pages/1_Live_Analysis.py.
        Required keys: ticker, company, quarter, earnings_date, source_label,
        scores, guidance, linguistics, sentiment, price_impact, yoy.

    Returns
    -------
    bytes
        Raw PDF bytes suitable for st.download_button.
    """
    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles  = _styles()
    story   = []

    ticker       = result.get("ticker", "")
    company      = result.get("company", ticker)
    quarter      = result.get("quarter", "Latest")
    earn_date    = result.get("earnings_date", "")
    source_label = result.get("source_label", "")
    sector       = result.get("sector", "")

    scores   = result.get("scores", {})
    guidance = result.get("guidance", {})
    ling     = result.get("linguistics", {})
    sent     = result.get("sentiment", {})
    pi       = result.get("price_impact", {})
    yoy      = result.get("yoy", {})
    qa_sc    = result.get("qa_scores")
    surps    = result.get("earnings_surprises", [])
    kp       = guidance.get("key_phrases", [])

    mci = scores.get("management_confidence_index", 0)
    drs = scores.get("deception_risk_score", 0)
    gs  = guidance.get("guidance_score", 0)
    ret = pi.get("next_day_return")

    # ── Header ─────────────────────────────────────────────────────────────────
    story.append(Paragraph("EarningsSense", styles["small"]))
    story.append(Paragraph(f"{ticker} - {company}", styles["h1"]))
    meta_parts = [p for p in [quarter, earn_date, sector, source_label] if p]
    story.append(Paragraph(" · ".join(meta_parts), styles["small"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
    story.append(Spacer(1, 0.3 * cm))

    # ── KPI scores ─────────────────────────────────────────────────────────────
    story.append(_kpi_table(mci, drs, gs, ret, styles))
    story.append(Spacer(1, 0.3 * cm))

    # YoY interpretation
    if yoy.get("trend") and yoy.get("trend") != "no_prior":
        trend_text = f"YoY Trend: {yoy['trend'].upper()} - {yoy.get('interpretation', '')}"
        story.append(Paragraph(trend_text, styles["small"]))
        story.append(Spacer(1, 0.2 * cm))

    # Sector benchmark
    sb = result.get("sector_bench", {})
    if sb.get("count", 0) > 0:
        mci_diff = mci - sb["avg_mci"]
        drs_diff = drs - sb["avg_drs"]
        bench_text = (
            f"Sector benchmark ({sector}, n={sb['count']}): "
            f"MCI {mci_diff:+.1f} vs avg {sb['avg_mci']:.1f} | "
            f"DRS {drs_diff:+.1f} vs avg {sb['avg_drs']:.1f}"
        )
        story.append(Paragraph(bench_text, styles["small"]))
        story.append(Spacer(1, 0.2 * cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))

    # ── FinBERT Sentiment ──────────────────────────────────────────────────────
    if sent:
        story.append(Paragraph("FinBERT Sentiment", styles["h2"]))
        story.append(_sentiment_table(sent))
        story.append(Spacer(1, 0.3 * cm))

    # ── Linguistic Metrics ─────────────────────────────────────────────────────
    if ling:
        story.append(Paragraph("Linguistic Metrics", styles["h2"]))
        story.append(_linguistics_table(ling))
        story.append(Spacer(1, 0.3 * cm))

    # ── Q&A Comparison ─────────────────────────────────────────────────────────
    if qa_sc:
        story.append(Paragraph("Prepared Remarks vs. Q&A Session", styles["h2"]))
        story.append(Paragraph(
            "Management language under analyst questioning vs. scripted remarks.",
            styles["small"],
        ))
        story.append(Spacer(1, 0.15 * cm))
        story.append(_qa_table(mci, drs, qa_sc["management_confidence_index"],
                               qa_sc["deception_risk_score"]))
        story.append(Spacer(1, 0.3 * cm))

    # ── Guidance ───────────────────────────────────────────────────────────────
    if kp:
        story.append(Paragraph("Key Guidance Phrases", styles["h2"]))
        for phrase in kp[:8]:
            story.append(Paragraph(f'"{phrase}"', styles["phrase"]))
            story.append(Spacer(1, 0.1 * cm))
        story.append(Spacer(1, 0.2 * cm))

    # ── EPS Surprise ───────────────────────────────────────────────────────────
    if surps:
        story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
        story.append(Paragraph("EPS Actual vs. Estimate", styles["h2"]))
        story.append(_eps_table(surps))
        story.append(Spacer(1, 0.3 * cm))

    # ── Post-earnings returns table ─────────────────────────────────────────────
    returns = [
        ("Next Day",   pi.get("next_day_return")),
        ("5-Day",      pi.get("five_day_return")),
        ("30-Day",     pi.get("thirty_day_return")),
    ]
    ret_rows = [(label, f"{v * 100:+.2f}%") for label, v in returns if v is not None]
    if ret_rows:
        story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
        story.append(Paragraph("Post-Earnings Price Returns", styles["h2"]))
        data = [["Period", "Return"]] + ret_rows
        col_w = [6 * cm, 4 * cm]
        t = Table(data, colWidths=col_w)
        t.setStyle(_TS_BASE)
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

    # ── Text snippet ───────────────────────────────────────────────────────────
    snippet = result.get("snippet", "")
    if snippet:
        story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
        label = result.get("snippet_label", "Text Snippet")
        story.append(Paragraph(label, styles["h2"]))
        story.append(Paragraph(snippet[:500] + "...", styles["body"]))
        story.append(Spacer(1, 0.3 * cm))

    # ── Footer ─────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
    story.append(Spacer(1, 0.2 * cm))
    today = date.today().strftime("%B %d, %Y")
    story.append(Paragraph(
        f"Generated by EarningsSense on {today}. "
        "For informational purposes only. Not financial advice. "
        "Past performance is not indicative of future results.",
        styles["footer"],
    ))

    doc.build(story)
    return buf.getvalue()
