# Data and collection

This guide describes the source data, their historical coverage and the path from downloaded records to the event-level R models.

## Main collection: 2020–2025

# Enlarged 2020–2025 sample: frame, design and execution

## Research purpose

The **2020–2025 cohort is the new primary sample**. The original 2015–2019 pilot is retained as a separately estimated historical replication, not naively pooled with its score-stratified events. The unit of inference is the review event / matched musician page, not 113 independent daily observations.

The enlarged data pipeline contributes five distinct data layers:

| Layer | Candidate source | Temporal coverage | Model role | Local path |
|---|---|---|---|---|
| Pitchfork review inventory | [The Fork](https://github.com/olievans123/The-Fork), `albums.json` (third-party archive) | Repository reports 1999–2026 | scores, dates, artists, genres, BNM; stratified frame | `data/downloads/pitchfork-modern/` |
| Artist/album identities and release timing | [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API) and Wikidata links | historical metadata | verify album/artist; review-minus-first-release days | `data/cache/musicbrainz/` |
| Wikipedia pageviews | [Wikimedia Pageviews API](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html) | 2015-07 onward | attention event outcome [-56,+56] and prior popularity [-180,-61] | `data/raw/wikipedia/`, `data/processed/popularity/` |
| Spotify worldwide chart | [Artıktay 2026 Zenodo](https://zenodo.org/records/23644526) | weekly 2018–2026 | Top 200 artist/song chart visibility and pre-history | `data/downloads/charts-modern/spotify/` |
| YouTube worldwide chart | same source | weekly 2018–2026 | Top 100 song/artist visibility and pre-history | `data/downloads/charts-modern/youtube/` |

**Data consistency:** use Zenodo record `23644526` (v1.0.0; 25 Oct 2026) so that checksums in `download_modern_charts.py` remain valid. A newer record version may exist: update the checksum, snapshot and citation intentionally instead of silently mixing files.

## Sample selection

1. Include review dates 2020-01-01 through 2025-12-31, scores from 0 to 10, and nonempty artist and album. Retain the full 1999–2026 catalogue as career-history reference.
2. Deduplicate on normalized **artist + album + review date**, preserving the rejected rows in an audit file. Review dates are NOT album release dates.
3. For each *year × score stratum*, select by the fixed SHA-256 hash of the event ID (`<5`, `5–<8`, `>=8`); default is at most **35 reviews in each cell**, i.e. at most 630 events across 6 years. Counts are targets, not observed sample claims. Each cell's known selection probability is recorded.
4. Resolve identities through MusicBrainz release-group and artist identifiers; use explicit overrides for ambiguous artists. Verify music releases/reissues separately.
5. Obtain 113 days of event-time Wikipedia views. Missing days are missing, not 0. Export an audit of unsuccessful requests; don't infer complete-window sample size from the 630 selected requests.
6. Compute all attention outcomes, Year FE, release-lag controls, clustered inference, RQ2 and dynamics in R.
7. Analyze global Spotify/YouTube charts on their own matched samples, retaining missing-identity and missing-calendar flags.

Score strata oversample unusually poor reviews on purpose. `selection_probability` permits a **known sampling-design sensitivity check**. Reweighting does not solve Wikipedia identity/coverage selection. The primary regression remains an event-level descriptive conditional association.

## Detailed collection commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
Rscript scripts/install_r_packages.R

# 1. Modern review catalogue and fixed frame
python scripts/download_extended_reviews.py
python scripts/prepare_extended_reviews.py --start-year 2020 --end-year 2025 --per-cell 35

# 2. MusicBrainz identity resolution, review date versus album release
python scripts/resolve_musicbrainz.py --email researcher@university.edu

# 3. Wikimedia short-term attention: event day -56 through +56
python scripts/prepare_wiki_manifest.py --events data/processed/review_enriched.csv --output data/processed/wiki_manifest.csv
python scripts/fetch_wikimedia_pageviews.py --manifest data/processed/wiki_manifest.csv --output data/raw/wikipedia
python scripts/build_event_panel.py

# 4. More distant pre-review baseline, event day -180 through -61
python scripts/collect_prior_popularity.py --email researcher@university.edu

# 5. Spotify and YouTube global charts including prior years for lookback
python scripts/download_modern_charts.py --platform both --start-year 2018 --end-year 2025
python scripts/analyze_modern_charts.py

# 6. RQ1, RQ2, RQ1-consumption, text add-on and figures
Rscript run_r.R --stage all
```

To avoid re-downloading the same source, the scripts recognize existing source files; Wikimedia API responses are cached. Run from the repository root. Dataset audit files and research outputs are intentionally ignored by Git.

## Expected outputs

- `data/processed/modern_review_census.csv`: full valid third-party review inventory with score strata and source IDs.
- `data/processed/modern_sampling_audit.csv`: eligible and selected counts for each year × score cell.
- `data/processed/review_sample.csv`: sampled review events and **prior critical-recognition** history.
- `data/processed/review_enriched.csv`: MusicBrainz identity and release date match result, including match statuses.
- `data/processed/pageview_coverage.csv`: API availability audit; `attention_complete_sample.csv`: eligible complete event sample.
- `data/processed/popularity/prior_wikipedia_popularity.csv`: distant baseline; not contemporaneous post-release Wikipedia metric.
- `data/processed/popularity/{spotify,youtube}_modern_event_chart_metrics.csv`: prior chart standing and observed review-window outcomes, with separate missing-calendar flags.
- `outputs/r/RQ1_year_adjusted_regressions.csv`, `RQ1_known_sampling_weights.csv` (if available), `RQ2_strict_prior_popularity_regressions.csv`, `RQ1_modern_chart_coefficients.csv`, plus the existing figures and group analyses.



## Historical dataset and file dictionary

# Dataset inventory, sample construction & codebook

## 1. Data lineage

| Stage | Source / step | Main local file | Unit of observation |
| --- | --- | --- | --- |
| Original reviews | Pinter et al. / Zenodo 3603330 | `data/downloads/pitchfork/output-data.csv` | Raw review row |
| Review frame | `scripts/prepare_reviews.py` | `data/processed/eligible_reviews.csv` | Deduplicated review event |
| Preselected API sample | Same; score strata and fixed SHA256 | `data/processed/review_sample.csv` | Review event |
| Artist/release metadata | MusicBrainz + Wikipedia/Wikidata links | `data/processed/review_enriched.csv` | Review event |
| Daily visitor requests | Wikimedia Pageviews API | `data/raw/wikipedia/{reviewid}.json` | Source response per review |
| Daily event panel | `scripts/build_event_panel.py` | `data/processed/pageview_panel.csv` | Review × event day |
| Complete-window sample | Same | `data/processed/attention_complete_sample.csv` | Review event |
| Regression variables | `src/online_analysis.py` | `outputs/events_model_data.csv` | Review event |
| Spotify chart archive | younver GitHub | `data/downloads/spotify/spotify-top-200-dataset.csv` | Artist × track × chart week |
| Spotify matched panel | `src/spotify_from_downloads.py` | `outputs/spotify_chart_week_panel.csv` | Review × event chart week |

The ZIP deliberately contains **source code and documentation only**. `data/` is populated by commands; no research CSV is required for installation or tests.

## 2. Review variables

Source: `artist`, `album`, `reviewdate`, `score`, `genre`, `releaseyear`, `reviewauthor`, `recordlabel`, and Spotify **audio features** (such as `danceability`, `valence`, `tempo`). Audio features do not measure historical demand.

Prepared columns:

| Variable | Definition |
| --- | --- |
| `reviewid` | `p4k_{one-based-source-row:08d}`; stable across repeat downloads of the published original file |
| `pub_date` | ISO review publication date, UTC date precision only |
| `title` | Album title from `album` |
| `score` | Published rating, 0–10 |
| `artist_norm`, `title_norm` | NFKC-normalized casefolded keys for candidate matching |
| `dedupe_key` | Artist + album + publication date |
| `score_stratum` | `low`: score <5; `middle`: 5≤score<8; `high`: ≥8 |
| `selection_hash` | SHA256 of `20261022|reviewid`, ranked within score stratum |
| `selection_probability` | Selected / eligible events in each stratum |
| `genres_json` | List-style genre representation for previous-sample schema compatibility |

**Verified source counts, 2018–2019:** 18,403 original rows contain 2,123 period rows; after removing nine period duplicates, 2,114 deduplicated review events remain: low 66, middle 1,619, high 429. Select 66 per stratum to form a pre-API sample of **198**, matching all 198 IDs from the earlier research dataset under the same stable rule.

## 3. Identity and release fields

`resolve_musicbrainz.py` stores:

- `musicbrainz_release_group_mbid`: MusicBrainz candidate release-group ID;
- `artist_mbid`: uniquely linked artist ID;
- `musicbrainz_first_release_date`: earliest release-group date, retaining source precision;
- `musicbrainz_first_release_date_precision`: `year`, `month`, or `day`;
- `musicbrainz_release_to_review_days`: only computed for a full day-level date;
- `wiki_wikipedia_title`: linked English Wikipedia article title (MusicBrainz URL or Wikidata sitelink);
- `match_status`, `candidate_count`, `candidate_mbids`: identity audit information.

Provide overrides for articles not linked by MusicBrainz with a local UTF-8 CSV:

```csv
artist,wiki_wikipedia_title
An Example Artist,An Example Artist (musician)
```

The override file is local research data and is not committed. Review its contents manually before collecting article traffic.

## 4. Wikipedia event panel

A single event is a professional album review, not an independent artist-year. A full window spans **113 calendar days**, relative day −56 through +56.

| Field | Type | Meaning |
| --- | --- | --- |
| `reviewid` | string | Source review ID |
| `event_day` | integer | Days relative to review publication |
| `date` | YYYY-MM-DD | UTC daily traffic date |
| `wiki_title` | string | Canonical or research-verified page title |
| `views` | nonnegative integer or missing | Daily access count |
| `observed` | 0/1 | API returned a record for that day |
| `full_window` | 0/1, in audit | All 113 observations present |

Missing days remain missing in `pageview_panel.csv`, and the analysis keeps fully observed windows. The sampling unit for regression remains the **event**, while Wikipedia-page cluster identity accounts for repeated events on the same page.

## 5. Derived event features and outcomes

| Variable | Formula / window |
| --- | --- |
| `baseline` | Mean `log(1+views)` on days −28…−8 |
| `trend_week` | 7 × OLS slope of log views on `event_day` in baseline |
| `preweek_delta` | Mean log views days −7…−1 minus baseline |
| `short_delta` | Mean log views days 0…6 minus baseline |
| `short_no_day0_delta` | Mean log views days 1…7 minus baseline |
| `mid_delta` | Mean log views days 7…27 minus baseline |
| `long_delta` | Mean log views days 28…55 minus baseline |
| `increment` | Mean log views 0…6 minus mean −7…−1 |
| `short_abs_delta` | Mean raw visits 0…6 minus mean −28…−8 |
| `abnormal_pre7` | Mean forecast residual −7…−1 after estimating prior 49-day trend + weekday controls |
| `abnormal_post7` | Mean forecast residual 0…6 |
| `abnormal_increment` | `abnormal_post7` − `abnormal_pre7` |
| `release_lag` | Review date minus MusicBrainz earliest day-level release date |
| `x`, `x2` | Score−7 and its square |
| `lowpop` | Indicator that prior baseline attention ≤ median |
| `x_lowpop` | Rating × low-pop interaction |

## 6. Spotify archive and event data

Raw Spotify archive uses the **semicolon separator**, not the comma used by Pitchfork; the parser reads it accordingly. Important columns: `artist_id`, `artist_name`, `album_id`, `album_name`, `track_id`, `rank`, `week`, `streams`, `pivot`.

After deduplication at `(artist_id, track_id, chart_week)` and unambiguous exact-name artist matching, each review is paired with eight chart weeks before and eight chart weeks at/after the review date. Aggregated outcomes include:

- `artist_top200_visible`: a chart-week includes at least one song crediting the reviewed artist;
- `album_top200_visible`: at least one reviewed-album track appears on the chart;
- `charted_track_streams` and `album_streams`: stream counts **inside the archived Global Top 200**;
- event-level `presence_delta` / `album_presence_delta`: mean post- minus pre-review chart visibility.

A review event need not have a Spotify match; unmatched and ambiguous cases remain visible in `spotify_artist_matching_audit.csv`. The archive's `week` label is retained in the panel and the relevant Spotify weekly ranking convention should be checked when doing fine-grained day-of-publication inference.

## 7. Reproduction targets from the earlier 196-event project

The earlier dataset contained **53 complete events (2015–2017)** and **143 complete events (2018–2019)**, with **22,148 daily traffic observations**. A separate consumption analysis had **132 pre-charted candidate review events**, and album-name matching identified **89** reviewed-album candidates. These historical sample counts are described in the earlier pre-analysis reports. Legacy Python replication scripts are retained once in `src/`. This public-data repository can recreate the 198 review IDs exactly, and then regenerates entity-matched panels from live API data.
