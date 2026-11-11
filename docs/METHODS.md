# R econometric specification (social science, not prediction)

This document is the empirical counterpart to [research design](RESEARCH.md). Executable specifications live in `R/`. Review *i* is the observation; the daily Wikipedia panel is used to construct review-level outcomes. The principal cohort is 2020–2025; 2018–2019 serves as a historical replication.

## RQ1. Criticism, attention, and persistence

### Variables and event windows

For review *i*, day *t*, let `v_it` be observed English Wikipedia page views and `l_it = log(1+v_it)`.

- `baseline = mean(l_i,t)` on days −28 to −8.
- `trend_week = 7 × OLS slope(l_i,t ~ t)` on days −28 to −8.
- `preweek_delta = mean(l_i,t, -7:-1) − baseline`.
- `short_delta = mean(l_i,t, 0:6) − baseline`.
- `short_no_day0_delta` uses days 1–7 instead.
- `mid_delta` uses 7–27; `long_delta` uses 28–55.
- `increment = mean(l_i,t, 0:6) − mean(l_i,t, -7:-1)`, distinguishing another week of escalation from a naive pre/post difference.
- `short_abs_delta = mean(v_i,t, 0:6) − mean(v_i,t, -28:-8)` keeps results in daily visits.

The event date is the reported *calendar date* of the review, not the exact time of publication; Wikipedia operates in UTC. No absent API observation is recoded as zero: the main event cohort requires all 113 days from −56 through +56.

### Main explanatory models

Define `x_i = PitchforkScore_i − 7`.

| Spec | Formula | Research interpretation | R output |
|---|---|---|---|
| M1 | `short_delta ~ x` | Unconditional score association | `RQ1_regressions.csv` |
| M2 | `short_delta ~ x + x²` | Curvature / extremity | same |
| **M3L** | `short_delta ~ x + baseline + trend_week` | **Main conditional association** | same |
| M3 | `short_delta ~ x + x² + baseline + trend_week` | Is there a supported U shape? | `RQ1_U_shape_diagnostic.csv` |
| Increment | `increment ~ x + baseline + trend_week` | Within-calendar-period additional change | `RQ1_dynamics.txt` |
| Placebo | `preweek_delta ~ x + baseline + trend_week` | Does the score predict *pre-publication* attention? | same |
| Dynamic | `mid_delta / long_delta ~ x + baseline + trend_week` | Persistence of association | same |

The estimand is the conditional mean score–attention association. Regressions use `fixest::feols`; `vcov = ~page_key` clusters at the resolved Wikipedia page so multiple reviews associated with one page do not count as independent shocks. Include the numbers of events and distinct page clusters with each regression; avoid using daily panel rows as the sample size.

### Genuine U-shape diagnosis

A quadratic curve is insufficient to establish a U shape. If the model is `Y_i = α + β₁x_i + β₂x_i² + ...`, compute derivative `β₁ + 2β₂x` at the actual lowest and highest observed score. For a U shape, left-end slope must be negative, right-end slope positive, and the turn `score* = 7 − β₁/(2β₂)` should lie within the observed score support. `R/helpers.R::u_shape_diagnostic()` computes both one-sided endpoint p-values with a joint intersection–union p-value `max(p_left,p_right)`, using the cluster covariance matrix. Report the coefficient and endpoint test together. Score thresholds `<5`, `5–<8`, `>=8` are sampling conventions rather than empirically established positive/negative sentiment cutoffs.

### Abnormal attention as an alternative outcome

Within each *complete* review event, fit a separate OLS **using only days −56 to −8 (49 days)**:

`log(1+views_it) = a_i + b_i · day_t + weekday fixed effects + e_it`

Then take mean observed minus predicted daily log views on days −7 to −1, 0–6, and 28–55. The main extensions are `abnormal_post7` and `abnormal_increment = abnormal_post7 − abnormal_pre7`. This subtracts predictable prior trending and weekday patterns. The corresponding forecast is a descriptive time-series baseline, not evidence of an unaffected control group.

### Release confounding and robustness

With MusicBrainz's release-date lag `d_i = review_date − earliest_release_date` (days), define `R_i = sign(d_i)·log(1+|d_i|)` and `D_i = 1(|d_i| <= 7)`. Fit `short_delta ~ x + baseline + trend_week + R_i + D_i` on exactly the same release-dated subsample. Restrict to `−28 <= d_i <= 365` for recent releases and/or exclude the ±7-day overlap. Alternative baseline periods `[−56,−8]` and `[−7,−1]` change the outcome definition; report them separately rather than selecting whichever is significant. `R/06_robustness.R` produces these tables.

## RQ2. Prior visibility, genre, and inequality

The primary continuous interaction is

`short_delta_i = α + β·x_i + γ·(baseline_i − median baseline) + δ·x_i·(baseline_i − median baseline) + η·trend_week_i + e_i`

`δ` is the difference in the **score–attention association** by baseline visibility. The simpler binary interaction uses `lowpop = 1(baseline < median)`. Examine absolute attention as well: `asinh(short_abs_delta)` handles negative absolute changes. For description, split prior popularity into terciles and show both relative log visits and **average absolute daily visit gains**. For genre heterogeneity, pool rare genres into Other, maintain Rock and Hip-Hop where counts are adequate, and use `x × genre` coefficients.

This distinguishes *relative discovery* from *absolute attention capture*: a niche artist may gain a larger proportional response while a major artist gains more daily visits. See `R/04_rq2_heterogeneity.R` and the corresponding RQ2 figures.

## Matched comparison and identification

Select only high-score (`>=8`) and low-score (`<5`) reviews. Use `MatchIt` nearest-neighbor propensity-score matching (`1:1`, without replacement, 0.2 standardized propensity-score caliper) on **pre-review baseline and trend**, and an additional version with release lag when present. Use `cobalt` standardized mean differences (SMD) to check covariate balance. `R/05_matching.R` estimates a **matched comparison of additional week-to-week attention change** (`increment`), with uncertainty clustered by matched pair.

Report matching as a *matched high-versus-low score contrast*. Since every event has a Pitchfork review, this is not a reviewed-versus-unreviewed DID.

## Consumer outcomes (Spotify)

`src/spotify_from_downloads.py` produces `outputs/spotify_review_summary.csv` and an event-week panel; R then uses chart visibility outcomes:

`presence_delta ~ x + pre_artist_visible`

`album_presence_delta ~ x + pre_album_visible`

Cluster errors by matched Spotify artist ID. The second dependent variable is the share of Top 200 calendar weeks with **songs assigned to the reviewed album**, based on conservative album-title joins. `album_streams_change` is a transformation of *chart-visible* track streams, never total streams, album sales or subscriber conversion. A weekly absence is unobserved below chart threshold, not zero playback.

## Pre-specified core tables / figures

- RQ1: score distribution, event-time trajectories, preweek/postweek/long-term, M1–M3L/M3, U-shape endpoint tests, abnormal attention.
- RQ2: interactions with initial popularity, relative vs absolute daily attention, genre, matched covariate balance.
- Consumption: artist and reviewed-album visibility, release timing sensitivity.
- Robustness: alternate dates/windows, release controls, pre-review placebo; report which hypotheses were exploratory.

Use the generated `.csv` tables in `outputs/r/` to prepare the poster. The `R/08_summary.R` script writes a compact findings memo from computed estimates instead of hard-coding conclusions.

## Text-as-Data extension (optional)

The main explanatory models remain RQ1/RQ2 with clustered inference. An optional social-science extension in [`R/09_text_analysis.R`](../R/09_text_analysis.R) adds professional-review prose features (score-conditional polarity, evaluative intensity, negative sentence share and cultural framing lexicons) and a separately sourced YouTube public-comment trajectory.

```bash
python scripts/download_review_text.py
python scripts/prepare_review_text.py
Rscript run_r.R --stage text
```

See [TEXT_AS_DATA.md](TEXT_AS_DATA.md) for the optional text evidence. Professional prose tone and the score are determined together; post-review audience tone is analyzed as a secondary outcome rather than as a pre-treatment control.
