# Optional Text-as-Data extension | expert review language and public reactions.
# It joins freshly constructed event outcomes to locally acquired numeric text
# features. This module does not require a text corpus for the main RQ1/RQ2 runs.
source("R/helpers.R")
check_dependencies(); ensure_dirs()

model_file <- "outputs/r/events_model_data.csv"
if (!file.exists(model_file)) stop("Run Rscript run_r.R --stage prepare before text analysis")
events <- main_events(read_csv_checked(model_file,
                     c("reviewid", "score", "x", "baseline", "trend_week",
                       "short_delta", "lowpop", "page_key")))
events$reviewid <- as.character(events$reviewid)

expert_file <- "data/processed/review_text_features.csv"
if (file.exists(expert_file)) {
  txt <- read_csv_checked(expert_file, c("reviewid", "text_sentiment_mean", "text_sentiment_abs",
                                       "text_negative_share", "text_word_count"))
  txt$reviewid <- as.character(txt$reviewid)
  if (anyDuplicated(txt$reviewid)) stop("Text feature table must have exactly one row per matched review ID")
  z <- merge(events, txt, by = "reviewid")
  z <- z[is.finite(z$text_sentiment_mean), , drop = FALSE]
  m <- list(
    ToneWithScore = safe_feols(short_delta ~ x + text_sentiment_mean + baseline + trend_week,
                               z, min_n = 20L, min_groups = 15L),
    NegativeLanguage = safe_feols(short_delta ~ x + text_negative_share + baseline + trend_week,
                                 z, min_n = 20L, min_groups = 15L),
    LanguageIntensity = safe_feols(short_delta ~ x + text_sentiment_abs + baseline + trend_week,
                                  z, min_n = 20L, min_groups = 15L),
    ToneByPriorPopularity = safe_feols(short_delta ~ x + text_sentiment_mean * lowpop + baseline + trend_week,
                                      z, min_n = 25L, min_groups = 20L)
  )
  if ("text_innovation_rate_1000" %in% names(z)) {
    m$InnovationFraming <- safe_feols(short_delta ~ x + text_innovation_rate_1000 + baseline + trend_week,
                                     z, min_n=20L, min_groups=15L)
  }
  if ("text_controversy_rate_1000" %in% names(z)) {
    m$ControversyFraming <- safe_feols(short_delta ~ x + text_controversy_rate_1000 + baseline + trend_week,
                                      z, min_n=20L, min_groups=15L)
  }
  coefs <- dplyr::bind_rows(lapply(names(m), function(label)
    tidy_feols(m[[label]], label, "short_delta", "review_text_matched")))
  write_csv_safe(coefs, "outputs/r/TEXT_review_language_regressions.csv")
  write_model_table(m, "outputs/r/TEXT_review_language_models.txt")
  coverage <- data.frame(primary_events = nrow(events), matched_full_review_text = nrow(z),
                         pct_covered = 100 * nrow(z) / nrow(events),
                         n_pages = length(unique(z$page_key)))
  write_csv_safe(coverage, "outputs/r/TEXT_review_language_coverage.csv")
  if (nrow(z) > 0L) {
    p <- ggplot2::ggplot(z, ggplot2::aes(score, text_sentiment_mean)) +
      ggplot2::geom_point(alpha = .5) + ggplot2::geom_smooth(method = "lm", se = TRUE) +
      ggplot2::labs(title = "Expert review tone and numerical evaluation",
                    x = "Pitchfork score", y = "Mean sentence-level polarity") + research_theme()
    save_plot(p, "11_score_vs_expert_review_tone.png")
    p2 <- ggplot2::ggplot(z, ggplot2::aes(text_sentiment_mean, short_delta)) +
      ggplot2::geom_point(alpha = .55) + ggplot2::geom_smooth(method = "lm", se = TRUE) +
      ggplot2::labs(title = "Review language and short-run attention",
                    subtitle = "Unadjusted scatterplot; adjusted estimates in TEXT_review_language_regressions.csv",
                    x = "Mean sentence-level polarity", y = "Short-run log attention change") +
      research_theme()
    save_plot(p2, "12_review_tone_and_attention.png")
    if ("text_innovation_rate_1000" %in% names(z)) {
      p3 <- ggplot2::ggplot(z,ggplot2::aes(baseline,text_innovation_rate_1000)) +
        ggplot2::geom_point(alpha=.5) + ggplot2::geom_smooth(method="lm",se=TRUE) +
        ggplot2::labs(title="Innovation discourse and prior visibility",
          x="Pre-review baseline log pageviews",y="Innovation-frame mentions / 1,000 words") +
        research_theme()
      save_plot(p3,"15_innovation_discourse_and_popularity.png")
    }
  }
  cat("TEXT expert-review analysis:",nrow(z),"matched events\n")
} else {
  cat("TEXT expert-review input absent: run python scripts/prepare_review_text.py\n")
}

comment_file <- "data/processed/youtube_comment_daily.csv"
if (file.exists(comment_file)) {
  c <- read_csv_checked(comment_file, c("reviewid", "event_day", "comment_count",
                                      "comment_sentiment_mean", "comment_negative_share"))
  c$reviewid <- as.character(c$reviewid)
  c <- merge(c, events[,c("reviewid","score","page_key")], by="reviewid")
  c$event_day <- as.integer(c$event_day)
  c <- c[is.finite(c$event_day) & c$event_day >= -28 & c$event_day <= 28, , drop=FALSE]
  c$score_group <- score_group(c$score)
  # The API gives accessible, sampled public comments in a current snapshot.
  # Missing days are NOT filled as zeros; a censored history is not a full population.
  windows <- dplyr::bind_rows(lapply(split(c, c$reviewid), function(d) {
    p <- d[d$event_day >= -7 & d$event_day <= -1, , drop=FALSE]
    q <- d[d$event_day >= 0 & d$event_day <= 6, , drop=FALSE]
    npre <- sum(p$comment_count); npost <- sum(q$comment_count)
    data.frame(reviewid = d$reviewid[1], score_group = as.character(d$score_group[1]),
               pre7_collected_comments = npre, post7_collected_comments = npost,
               post7_sampled_sentiment = if(npost) weighted.mean(q$comment_sentiment_mean,
                                     q$comment_count) else NA_real_,
               post7_sampled_negative_share = if(npost) weighted.mean(q$comment_negative_share,
                                     q$comment_count) else NA_real_)
  }))
  write_csv_safe(windows,"outputs/r/TEXT_youtube_event_summary.csv")
  if (nrow(c) >= 3L) {
    daily <- c |>
      dplyr::group_by(event_day, score_group) |>
      dplyr::summarise(n_collected = sum(comment_count),
                       tone = stats::weighted.mean(comment_sentiment_mean, w=comment_count),
                       event_count = dplyr::n_distinct(reviewid), .groups="drop")
    write_csv_safe(daily, "outputs/r/TEXT_youtube_event_time.csv")
    p <- ggplot2::ggplot(daily, ggplot2::aes(event_day, tone, color=score_group)) +
      ggplot2::geom_line() + ggplot2::geom_point(size=1.2) +
      ggplot2::geom_vline(xintercept=0, linetype="dashed") +
      ggplot2::labs(title="Audience language among collected YouTube comments",
                    subtitle="Available comment snapshots; missing event-days not zero-filled",
                    x="Days relative to Pitchfork review",y="Mean polarity", color="Score group") +
      research_theme()
    save_plot(p,"13_audience_comment_tone.png")
    p2 <- ggplot2::ggplot(daily, ggplot2::aes(event_day, n_collected, color=score_group)) +
      ggplot2::geom_line() + ggplot2::geom_vline(xintercept=0,linetype="dashed") +
      ggplot2::labs(title="Observed YouTube comment volume in collected snapshot",
                    subtitle="Only retrieved comments, not a historical census of platform activity",
                    x="Days relative to Pitchfork review", y="Collected comment count", color="Score group") +
      research_theme()
    save_plot(p2,"14_audience_comment_volume.png")
  }
  cat("TEXT audience comments:",nrow(windows),"review events with sampled comments\n")
} else {
  cat("TEXT audience input absent: run python scripts/fetch_youtube_comments.py\n")
}
