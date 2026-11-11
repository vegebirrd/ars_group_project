"""Text-as-data features for expert reviews and independently sampled audience comments.

Transparent, interpretable sentence-level measures. TextBlob's lexicon-based polarity
is useful as a baseline and *not* a ground-truth music-quality or sarcasm classifier.
All original prose stays in the local inputs; this module exports numeric features.
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Any
import numpy as np
import pandas as pd

SENTENCES = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“‘])|\n{2,}")
WORDS = re.compile(r"\b[\w’-]+\b", flags=re.UNICODE)
# Exploratory discourse frames, NOT a trained topic/semantic model. Document all
# patterns so a researcher can inspect false positives in the local corpus.
FRAME_PATTERNS = {
    "innovation": re.compile(r"\b(?:experiment(?:al|ation|s)?|innovati(?:ve|on)|avant[ -]garde|boundary[ -]pushing|unconventional|adventurous|radical)\b", re.I),
    "commercial": re.compile(r"\b(?:commercial|mainstream|radio[ -]friendly|accessible|formulaic|marketable|chart[ -]friendly|pop[ -]appeal)\b", re.I),
    "controversy": re.compile(r"\b(?:controvers(?:y|ial)|polariz(?:ing|ation)|scandal|backlash|provocati(?:ve|on)|outrage(?:ous)?|notorious)\b", re.I),
}

def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    # Keep sentences as units so a lengthy factual review does not wash out
    # every strong positive or negative evaluative sentence.
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]

def lexicon_polarity(sentence: str, analyzer=None) -> float:
    if analyzer is not None:
        return float(analyzer(sentence))
    from textblob import TextBlob
    return float(TextBlob(sentence).sentiment.polarity)

def text_features(text: str, analyzer=None) -> dict[str, float]:
    sentences = split_sentences(text)
    words = WORDS.findall(str(text or ""))
    frame_rates = {f"text_{name}_rate_1000": (1000.0 * len(patt.findall(str(text))) / len(words)
                   if len(words) else np.nan) for name,patt in FRAME_PATTERNS.items()}
    if not sentences:
        return dict(text_word_count=0, text_sentence_count=0, text_sentiment_mean=np.nan,
                    text_sentiment_abs=np.nan, text_negative_share=np.nan,
                    text_positive_share=np.nan, text_sentiment_sd=np.nan, **frame_rates)
    pol = np.array([lexicon_polarity(s, analyzer) for s in sentences], dtype=float)
    return dict(text_word_count=len(words), text_sentence_count=len(sentences),
                text_sentiment_mean=float(pol.mean()), text_sentiment_abs=float(np.abs(pol).mean()),
                text_negative_share=float((pol < -0.05).mean()),
                text_positive_share=float((pol > 0.05).mean()),
                text_sentiment_sd=float(pol.std(ddof=0)), **frame_rates)

def extract_comment_rows(payload: dict[str, Any], video_id: str, reviewid: str,
                         pub_date: str) -> list[dict[str, Any]]:
    """Parse only top-level comments, preserving original timestamps and IDs.

    API is a current survivorship snapshot. Published date is not updated date.
    """
    reviewdate = pd.Timestamp(pub_date).date()
    rows = []
    for item in payload.get("items", []):
        snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        cid = item.get("snippet", {}).get("topLevelComment", {}).get("id", "")
        raw_date = snippet.get("publishedAt")
        if not (raw_date and cid):
            continue
        comment_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).date()
        rows.append(dict(reviewid=str(reviewid), video_id=str(video_id),
                         comment_id=str(cid), published_date=comment_date.isoformat(),
                         event_day=(comment_date-reviewdate).days,
                         text=str(snippet.get("textDisplay", "")),
                         like_count=int(snippet.get("likeCount", 0))))
    return rows

def summarize_comments(rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return observed-day aggregates and one record per reviewed event.

    Never fill absent day with a zero: search results might be truncated, removed,
    or incomplete for the requested review period.
    """
    needed={"reviewid","comment_id","event_day","text"}
    if needed-set(rows.columns): raise ValueError(f"Missing comment fields: {sorted(needed-set(rows.columns))}")
    cols=["reviewid","event_day","comment_count","comment_sentiment_mean","comment_negative_share","comment_sentiment_abs"]
    ec=["reviewid","youtube_pre7_count","youtube_post7_count","youtube_pre7_sentiment",
        "youtube_post7_sentiment","youtube_post_negative_share","youtube_post_sentiment_abs"]
    if rows.empty: return pd.DataFrame(columns=cols), pd.DataFrame(columns=ec)
    data=rows.drop_duplicates(["reviewid","comment_id"]).copy()
    data["event_day"]=pd.to_numeric(data["event_day"],errors="coerce")
    data=data.dropna(subset=["event_day"])
    data["polarity"]=data.text.map(lambda x: lexicon_polarity(str(x)))
    data["negative"]=(data.polarity < -0.05).astype(int)
    data["abs_polarity"]=data.polarity.abs()
    daily=(data.groupby(["reviewid","event_day"],as_index=False)
           .agg(comment_count=("comment_id","size"),
                comment_sentiment_mean=("polarity","mean"),
                comment_negative_share=("negative","mean"),
                comment_sentiment_abs=("abs_polarity","mean")))
    # Counts represent COLLECTED comments (not all comments ever posted).
    results=[]
    for rid,g in data.groupby("reviewid",sort=False):
        pre=g[g.event_day.between(-7,-1)]; post=g[g.event_day.between(0,6)]
        results.append(dict(reviewid=rid, youtube_pre7_count=len(pre), youtube_post7_count=len(post),
            youtube_pre7_sentiment=pre.polarity.mean() if len(pre) else np.nan,
            youtube_post7_sentiment=post.polarity.mean() if len(post) else np.nan,
            youtube_post_negative_share=post.negative.mean() if len(post) else np.nan,
            youtube_post_sentiment_abs=post.abs_polarity.mean() if len(post) else np.nan))
    return daily[cols],pd.DataFrame(results)[ec]
