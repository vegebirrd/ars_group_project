# Creates the R event-level analysis table *directly* from the Python collection
# pipeline's review sample and untransformed 113-day Wikipedia event panel.
# This intentionally recomputes outcomes independently from Python estimators.
source("R/helpers.R")
check_dependencies()
ensure_dirs()

reviews_path <- "data/processed/attention_complete_sample.csv"
panel_path <- "data/processed/pageview_panel.csv"
reviews <- read_csv_checked(reviews_path, c("reviewid", "score", "pub_date", "artist"))
panel <- read_csv_checked(panel_path, c("reviewid", "event_day", "date", "views", "observed"))

if (anyDuplicated(reviews$reviewid)) stop("Repeated reviewid in review sample")
if (anyDuplicated(panel[, c("reviewid", "event_day")])) stop("Repeated reviewid/event_day in pageview panel")
if (any(!is.na(panel$views) & panel$views < 0)) stop("Negative Wikipedia visits")

panel$date <- as.Date(panel$date)
panel$event_day <- as.integer(panel$event_day)
panel$views <- as.numeric(panel$views)
panel$observed <- as.integer(panel$observed)
panel <- panel[panel$reviewid %in% reviews$reviewid, , drop = FALSE]

wins <- list(baseline = c(-28, -8), preweek = c(-7, -1), short = c(0, 6),
             short_no_day0 = c(1, 7), mid = c(7, 27), long = c(28, 55))

one_event <- function(g) {
  g <- g[order(g$event_day), , drop = FALSE]
  if (nrow(g) != 113L || !identical(g$event_day, -56:56) ||
      any(is.na(g$observed)) || any(g$observed != 1L) ||
      anyNA(g$views) || anyNA(g$date)) return(NULL)
  g$log_views <- log1p(g$views)
  within_win <- function(rng) g[g$event_day >= rng[1] & g$event_day <= rng[2], , drop = FALSE]
  base <- within_win(wins$baseline)
  base_log <- mean(base$log_views)
  base_abs <- mean(base$views)
  coef_trend <- stats::coef(stats::lm(log_views ~ event_day, data = base))["event_day"]
  record <- list(reviewid = as.character(g$reviewid[1]), baseline = base_log,
                 baseline_abs_views = base_abs, trend_week = unname(coef_trend) * 7)
  for (w in names(wins)) {
    z <- within_win(wins[[w]])
    record[[paste0(w, "_log_mean")]] <- mean(z$log_views)
    record[[paste0(w, "_views_mean")]] <- mean(z$views)
    record[[paste0(w, "_delta")]] <- mean(z$log_views) - base_log
    record[[paste0(w, "_abs_delta")]] <- mean(z$views) - base_abs
  }
  record$increment <- record$short_log_mean - record$preweek_log_mean
  record$relative_week_log_ratio <- log((sum(within_win(c(0, 6))$views) + 7) /
                                          (sum(within_win(c(-7, -1))$views) + 7))

  # A separate counterfactual forecast is NOT identified here. This pre-period
  # trend + weekday model is a descriptive benchmark for abnormal attention.
  g$weekday <- factor(as.POSIXlt(g$date)$wday, levels = 0:6)
  pre <- within_win(c(-56, -8))
  forecast <- stats::lm(log_views ~ event_day + weekday, data = pre)
  g$abnormal_log <- g$log_views - as.numeric(stats::predict(forecast, newdata = g))
  pick <- function(a, b) mean(g$abnormal_log[g$event_day >= a & g$event_day <= b])
  record$abnormal_pre7 <- pick(-7, -1)
  record$abnormal_post7 <- pick(0, 6)
  record$abnormal_long <- pick(28, 55)
  record$abnormal_increment <- record$abnormal_post7 - record$abnormal_pre7
  list(event = as.data.frame(record, stringsAsFactors = FALSE), daily = g)
}

res <- lapply(split(panel, panel$reviewid), one_event)
res <- Filter(Negate(is.null), res)
if (!length(res)) stop("No complete 113-day review events; inspect pageview_coverage.csv")
summary <- dplyr::bind_rows(lapply(res, `[[`, "event"))
daily <- dplyr::bind_rows(lapply(res, `[[`, "daily"))
summary$reviewid <- as.character(summary$reviewid)
reviews$reviewid <- as.character(reviews$reviewid)
summary <- dplyr::left_join(summary, reviews, by = "reviewid", relationship = "one-to-one")
# Strictly pre-review popularity sources. Optional: the baseline model runs
# unchanged if these additional historical sources have not yet been fetched.
for (fname in c("data/processed/popularity/prior_wikipedia_popularity.csv",
                "data/processed/popularity/prior_spotify_visibility.csv")) {
  if (file.exists(fname)) {
    pdat <- readr::read_csv(fname, show_col_types = FALSE)
    if ("reviewid" %in% names(pdat)) {
      pdat$reviewid <- as.character(pdat$reviewid)
      if (anyDuplicated(pdat$reviewid)) stop(paste("Duplicate reviewid in", fname))
      summary <- dplyr::left_join(summary, pdat, by = "reviewid", relationship = "many-to-one")
    }
  }
}
# Optional 2018–2026 weekly global chart outcomes; prefix names per platform.
for (platform in c("spotify", "youtube")) {
  fname <- paste0("data/processed/popularity/", platform, "_modern_event_chart_metrics.csv")
  if (file.exists(fname)) {
    pc <- readr::read_csv(fname,show_col_types=FALSE)
    pc$reviewid <- as.character(pc$reviewid)
    stopifnot(!anyDuplicated(pc$reviewid))
    pc <- pc[,setdiff(names(pc),"platform"),drop=FALSE]
    names(pc)[names(pc)!="reviewid"] <- paste0(platform,"_",names(pc)[names(pc)!="reviewid"])
    summary <- dplyr::left_join(summary,pc,by="reviewid",relationship="many-to-one")
  }
}
summary$score <- as.numeric(summary$score)
summary$x <- summary$score - 7
summary$x2 <- summary$x^2
summary$score_group <- score_group(summary$score)
summary$year <- as.integer(format(as.Date(summary$pub_date), "%Y"))
# Prefer a stable page id; fallback to a canonical page title, then artist.
summary$page_key <- if ("wiki_wikipedia_title" %in% names(summary)) as.character(summary$wiki_wikipedia_title) else rep(NA_character_, nrow(summary))
missing_page <- is.na(summary$page_key) | !nzchar(trimws(summary$page_key))
summary$page_key[missing_page] <- as.character(summary$artist[missing_page])
summary$page_key <- paste0("enwiki:title:", tolower(trimws(summary$page_key)))
if ("wiki_pageid" %in% names(summary)) {
  ok <- !is.na(summary$wiki_pageid) & nzchar(trimws(as.character(summary$wiki_pageid)))
  summary$page_key[ok] <- paste0("enwiki:id:", as.character(summary$wiki_pageid[ok]))
}
summary$baseline_centered <- summary$baseline - stats::median(summary$baseline, na.rm = TRUE)
summary$lowpop <- as.integer(summary$baseline < stats::median(summary$baseline, na.rm = TRUE))
summary$asinh_abs_delta <- asinh(summary$short_abs_delta)
lag_name <- "musicbrainz_release_to_review_days"
summary$release_lag <- if (lag_name %in% names(summary)) as.numeric(summary[[lag_name]]) else NA_real_
summary$release_near7 <- ifelse(is.na(summary$release_lag), NA_real_, as.numeric(abs(summary$release_lag) <= 7))
summary$release_log_days <- sign(summary$release_lag) * log1p(abs(summary$release_lag))
raw_genre <- if ("genre" %in% names(summary)) as.character(summary$genre) else rep(NA_character_, nrow(summary))
if ("genres_json" %in% names(summary)) {
  needs <- is.na(raw_genre) | !nzchar(trimws(raw_genre))
  raw_genre[needs] <- as.character(summary$genres_json[needs])
}
raw_genre <- tolower(raw_genre)
summary$genre_group <- ifelse(is.na(raw_genre) | !nzchar(trimws(raw_genre)), "Unknown",
                        ifelse(grepl("hip[- ]?hop|rap", raw_genre), "Hip-Hop",
                        ifelse(grepl("rock", raw_genre), "Rock", "Other")))
summary$genre_group <- factor(summary$genre_group, levels = c("Other", "Rock", "Hip-Hop", "Unknown"))

summary$pub_date <- as.Date(summary$pub_date)
# Flag repeated-page reviews whose full 113-day event windows overlap.
summary$overlapping_page_event <- 0L
for (idx in split(seq_len(nrow(summary)), summary$page_key)) {
  if (length(idx) < 2L) next
  dates <- as.numeric(summary$pub_date[idx]); gaps <- abs(outer(dates, dates, "-"))
  diag(gaps) <- Inf
  summary$overlapping_page_event[idx] <- as.integer(apply(gaps <= 112, 1, any))
}
write_csv_safe(summary, "outputs/r/events_model_data.csv")
write_csv_safe(daily, "outputs/r/pageview_event_daily.csv")
write_csv_safe(data.frame(n_reviews = nrow(reviews), n_complete = nrow(summary),
                          n_pages = length(unique(summary$page_key)), n_daily = nrow(daily)),
               "outputs/r/coverage.csv")
cat("R data prepared:", nrow(summary), "events;", nrow(daily), "daily rows;",
    length(unique(summary$page_key)), "Wikipedia pages\n")
