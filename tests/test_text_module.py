"""Tests use only synthetic text and mock API JSON: no real scraped material."""
from __future__ import annotations
import pandas as pd
import pytest
from src.text_research import text_features,extract_comment_rows,summarize_comments
from scripts.prepare_review_text import link_text_reviews


def test_sentiment_feature_directions_with_stub():
    f=text_features('Wonderful music. Bad mixing. Neutral description.',
      analyzer=lambda t: 1.0 if 'Wonderful' in t else (-1.0 if 'Bad' in t else 0.0))
    assert f['text_sentence_count']==3
    assert f['text_sentiment_mean']==pytest.approx(0.0)
    assert f['text_sentiment_abs']==pytest.approx(2/3)
    assert f['text_negative_share']==pytest.approx(1/3)
    assert f['text_positive_share']==pytest.approx(1/3)
    assert 'text_controversy_rate_1000' in f


def test_full_review_identity_and_ambiguity():
    reviews=pd.DataFrame([dict(reviewid='r1',artist='Beyoncé',title='Alpha!',score=8.0,pub_date='2018-02-01'),
                          dict(reviewid='r2',artist='Tinashe',title='Beta',score=9.0,pub_date='2018-03-04')])
    corpus=pd.DataFrame([dict(artist='Beyonce',album='Alpha',rating=8.,release_date='2018-02-02',review='Excellent album.'),
                         dict(artist='Tinashe',album='Beta',rating=9.,release_date='2018-03-04',review='Wonderful album.'),
                         dict(artist='Tinashe',album='Beta',rating=9.,release_date='2018-03-05',review='Very poor album.')])
    # Unicode accent removal is handled for exact-identity candidate generation.
    feats,audit=link_text_reviews(reviews,corpus)
    assert len(feats)==1
    assert feats.reviewid.iloc[0]=='r1'
    assert audit.set_index('reviewid').loc['r2','status']=='ambiguous'
    assert 'text_body' not in feats.columns


def test_comment_date_is_published_date_not_updated_date():
    payload=dict(items=[dict(snippet=dict(topLevelComment=dict(id='a1',snippet=dict(
        textDisplay='Great album',publishedAt='2018-05-02T02:20:00Z',updatedAt='2024-01-01T00:00:00Z'))))])
    rows=extract_comment_rows(payload,'abcdefghijk','r1','2018-05-01')
    assert rows[0]['event_day']==1
    daily,event=summarize_comments(pd.DataFrame(rows))
    assert daily.event_day.iloc[0]==1
    assert event.youtube_post7_count.iloc[0]==1
    assert event.youtube_pre7_count.iloc[0]==0
    assert pd.isna(event.youtube_pre7_sentiment.iloc[0])


def test_audience_data_only_observed_days():
    rows=pd.DataFrame([dict(reviewid='r1',comment_id='c1',event_day=-2,text='Good.'),
                       dict(reviewid='r1',comment_id='c1',event_day=-2,text='Good.'),
                       dict(reviewid='r1',comment_id='c2',event_day=3,text='Bad.')])
    daily,event=summarize_comments(rows)
    assert daily.comment_count.sum()==2
    assert set(daily.event_day)=={-2,3}
    assert set(range(-7,7))-set(daily.event_day)  # not filled with zero
    assert event.youtube_pre7_count.iloc[0]==1
    assert event.youtube_post7_count.iloc[0]==1


def test_cultural_frame_rates_are_deterministic():
    x=text_features('An experimental, radical album. A mainstream, formulaic comeback.')
    assert x['text_innovation_rate_1000']>0
    assert x['text_commercial_rate_1000']>0
    assert x['text_controversy_rate_1000']==0
