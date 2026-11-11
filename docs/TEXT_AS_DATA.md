# Text-as-Data extension: professional evaluation and audience discourse

**Project:** *The Tinashe Effect or the Tyga Effect?*  
**Repository:** `ars_group_project`  
**Main outputs:** `data/processed/review_text_features.csv`, `data/processed/youtube_comment_daily.csv`, and `outputs/r/TEXT_*`

## 1. Research contribution and how it fits the original RQs

A Pitchfork score is an ordinal summary of an editor's judgment. The prose of the review may communicate evaluative **tone**, **intensity**, and **mixed feelings** that are not captured by the number alone. Public online comments are different: they represent **audience discourse**, not professional assessment. Treat these as two distinct measurements and do not merge them into one sentiment variable.

### RQ1: Attention Creation vs. Quality Signaling

- **H1 (evaluative tone):** Holding the published score constant, more positive professional language is associated with higher short-run artist attention.
- **H2 (intensity / controversy):** Stronger evaluative language (positive *or* negative) is associated with larger short-run attention changes. This differs conceptually from a mechanical U-shape in *scores*.
- **H3 (attention vs. reception):** Changes in sampled discussion volume and the tone of audience comments may diverge: negative publicity may generate curiosity without favorable reception.
- **H4 (persistence):** Test each language measure against separately defined days 0–6, 7–27 and 28–55 outcomes; attention creation and longer-term engagement need not track one another.

### RQ2: Cultural Gatekeeping / distribution of attention

- **H5 (artist prominence):** The association between professional tone and attention differs by the artist's **pre-review** Wikipedia baseline; estimate text-tone × low prior popularity.
- **H6 (genre):** A genre-stratified analysis is a *secondary* extension, only if cell sizes and matching coverage suffice; music terminology varies strongly by genre.

The foundational distinction is **measurement vs. identification**: correlating review language with subsequent pageviews is a valid descriptive social-science design, but the text is chosen together with the score, and album release / publicity may affect both the review and the audience. Post-review audience comments are **outcomes or mechanism indicators**, never exogenous controls in the main equation.

## 2. Literature ideas

1. **Berger, Sorensen & Rasmussen (2010), Marketing Science, 29(5), 815–827.** Negative publicity may increase awareness of relatively unknown products. This motivates score/tone × baseline popularity, rather than assuming all negative reviews discourage attention. https://doi.org/10.1287/mksc.1090.0557
2. **Chevalier & Mayzlin (2006), Journal of Marketing Research, 43(3), 345–354.** The tone and amount of consumer word-of-mouth can be studied alongside market outcomes. Their book-sales setting motivates treating audience discussion as a distinct social process from professional reviews. https://doi.org/10.1509/jmkr.43.3.345
3. **Gentzkow, Kelly & Taddy (2019), Journal of Economic Literature, 57(3), 535–574.** *Text as Data* motivates transparent feature construction, interpretation, preselected hypotheses and awareness of high-dimensional text/measurement problems. https://doi.org/10.1257/jel.20181020
4. **Pinter et al. (2020), ICWSM.** P4KxSpotify is the numerical score/metadata base. It does **not contain review bodies**; that content must be sourced separately. https://doi.org/10.1609/icwsm.v14i1.7355
5. **Kozlowski, Taddy & Evans (2019), American Sociological Review, 84(5), 905–949.** *The Geometry of Culture: Analyzing the Meanings of Class through Word Embeddings* motivates a later text-embedding analysis of taste and distinction, but is deliberately **not required** for this first implementation. https://doi.org/10.1177/0003122419877135
6. **Using word embedding models to capture changing media discourses (2022), Journal of Computational Social Science.** Uses Pitchfork text to study how music journalism organizes categories of legitimacy and genres; a closer domain-specific motivation for cultural gatekeeping. https://doi.org/10.1007/s42001-022-00182-8

## 3. Two separate data tracks

| Track | Unit | Source | Main variables | Research role |
|---|---|---|---|---|
| Expert text | Pitchfork review event | Optional third-party full-review text corpus | sentence-level polarity, positive/negative shares, absolute polarity, review length and three transparent discourse dictionaries | RQ1/RQ2 interpretive extension |
| Audience text | YouTube top-level comment | Official YouTube Data API v3 on **manually verified** album-related videos | publication date, review-relative time, collected volume, sampled sentiment | Audience discourse trajectory / exploratory mechanism |

**Public dataset candidates (researcher downloads locally):**

- **Preferred optional full-text source:** https://huggingface.co/datasets/mattismegevand/pitchfork — dataset lists `artist`, `album`, `release_date` (review date according to its card), `rating`, `review`.
- **Alternative corpus:** https://components.one/datasets/pitchfork-reviews-dataset and `text2map.corpora` documentation; its described 1999–January 2019 coverage does not extend across all 2019 events.
- **Historical numerical review metadata:** https://zenodo.org/records/3603330 — use this for the main cohort, not for review bodies.
- **YouTube comments:** https://developers.google.com/youtube/data/reference/rest/v3/commentThreads/list — `videoId`, `maxResults`, `pageToken`, `publishedAt`, `textDisplay`, `textFormat=plainText`.

Check source provenance and reuse terms; full review prose and personal comment text stay in ignored `data/` paths. Only **numeric features, schema, and code** belong in the public repository.

## 4. Step-by-step commands (macOS Terminal or VS Code; RStudio unnecessary)

Start with the regular cohort and Wikipedia panel:

```bash
python scripts/download_public_data.py pitchfork
python scripts/prepare_reviews.py
# For main outcomes, complete the Wikipedia/MusicBrainz pipeline described in README.
```

### Track A — expert Pitchfork full-text features

```bash
# ~90 MB optional full-text download (separate from numerical P4KxSpotify dataset):
python scripts/download_review_text.py
python scripts/prepare_review_text.py

# R must first have outputs/r/events_model_data.csv (built by R/01_prepare.R)
Rscript run_r.R --stage prepare
Rscript run_r.R --stage text
```

A full-text match requires normalized artist, album, review date (±3 days by default) and consistent score. Ambiguous title matches are **audited, not guessed**. Files:

- `data/processed/review_text_match_audit.csv`: `matched`, `unmatched`, `ambiguous`, per review ID.
- `data/processed/review_text_features.csv`: numeric text measures **without review bodies**.

### Track B — audience YouTube comments

```bash
python scripts/make_youtube_manifest.py
# Manually fill video_id (11 characters), video_title, verification fields in:
#   data/processed/youtube_video_manifest.csv

# Enable YouTube Data API v3 in Google Cloud, then in current Terminal:
export YOUTUBE_API_KEY='YOUR_OWN_API_KEY'
python scripts/fetch_youtube_comments.py --max-pages 3
Rscript run_r.R --stage text
```

Outputs:

- `data/raw/youtube/comments_local.csv` — raw sample of comment text stored only on your machine.
- `data/processed/youtube_comment_daily.csv` — **observed days only**, no artificial zeros.
- `data/processed/youtube_comment_event.csv` — sample-based before/after counts and polarity.
- `data/processed/youtube_collection_audit.csv` — per-video fetch success, page count, truncation indicator.

**Video choice:** prefer the officially uploaded song/album-related video, published *before the study window* if pre/post comparison is attempted. Do not automatically equate comments under a 2024 upload with consumer response to a 2018 record. If no relevant, contemporaneous video exists, the event remains unmatched.

**Historical coverage:** the API returns comments currently available, not an archived 2018 snapshot. `--max-pages` truncates the most recent-first pagination by design. That means retrieved counts are sampling/censoring-sensitive and should be labeled **collected comments**, not total historical comments. Comments deleted since 2018 are invisible. This module does not make zero-filled daily audience histories from incomplete API pages.

### Combined workflow

```bash
python scripts/run_text_pipeline.py --stage expert --download-review-text
# After filling YouTube manifest and setting key:
python scripts/run_text_pipeline.py --stage audience --max-pages 3
Rscript run_r.R --stage all
```

## 5. Variables, models and figures

Let `score_c = Pitchfork score − 7`, `B` be baseline log pageviews, and `T` pre-review trend.

**Expert-language extension, estimated on matched full-text sample:**

\[
\Delta_i^{0:6}=\alpha+\beta_s\,(score_i-7)+\beta_t\,Tone_i+\gamma B_i+\eta T_i+\epsilon_i.
\]

Additional exploratory discourse dictionaries tally mentions per 1,000 words of **innovation**, **commercial appeal** and **controversy** frames. A dictionary match is not a validated semantic interpretation; these rates are explicitly intended for human audit. Separate models replace `Tone` by `NegativeSentenceShare` or `MeanAbsoluteSentencePolarity`; never interpret a sentiment score as certified aesthetic quality. `Tone × LowPopularity` extends RQ2. `fixest` uses Wikipedia-page clustered SEs. Comparisons must be within the same matched sample: changing the sample from 143 events to fewer text-matched events alone can move estimates.

**Audience analysis:** event-time plots and sample-based descriptive indicators for collected comments. Do not control for post-event audience sentiment when interpreting review-score associations because that variable is temporally downstream. A future design could evaluate a clearly identified audience response as a second outcome with contemporaneous release controls.

All figures generated by `R/09_text_analysis.R`:

- `11_score_vs_expert_review_tone.png`
- `12_review_tone_and_attention.png`
- `13_audience_comment_tone.png`
- `14_audience_comment_volume.png`
- `15_innovation_discourse_and_popularity.png`

The R script also writes `TEXT_review_language_regressions.csv`, `TEXT_review_language_coverage.csv`, `TEXT_youtube_event_summary.csv`, and `TEXT_youtube_event_time.csv` when corresponding inputs are present.

## 6. Sensible extensions for a larger paper

**First priority:** manually label ~50–100 sampled texts for polarity, mixed judgment, sarcasm and artistic-innovation framing. Report inter-coder agreement and compare lexicon measures to human ratings. Musical language contains metaphor; a single polarity lexicon is deliberately only a baseline.

**Second priority:** add a modest, pre-specified cultural-distinction dictionary (e.g., *experimental*, *formulaic*, *accessible*, *commercial*, *challenging*) and have humans validate its precision. Or use an embedding model to produce document-level semantic themes with an audit trail. Link these to pre-review artist visibility (RQ2) rather than treating all low scores as scandal or outrage.

**Third priority:** obtain a permitted, genuinely longitudinal audience-comment dataset. YouTube and Reddit access policies differ; Reddit's academic research use requires an approved access route, not unauthorized scraping. https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data

## 7. Reproducibility checklist

- Fix the **analysis period**, comparison windows and release exclusions before evaluating significance.
- Retain text-match and video-selection audit tables; missing text is not missing at random.
- Avoid training language models on scraped copyrighted review bodies without rights.
- Treat Pitchfork rating and body as **co-produced** professional evaluations; their coefficients are conditional associations.
- Clearly separate professional reviews from consumer comments and total sales from chart-visible streams.
