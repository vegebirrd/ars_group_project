# Test the R pipeline on a small, explicitly synthetic event panel.
# All operations take place in tempdir(); no real research files are read/written.
source_dir <- normalizePath(getwd())
scratch <- tempfile("ars-r-test-")
dir.create(scratch, recursive = TRUE)
file.copy(file.path(source_dir, "R"), scratch, recursive = TRUE)
setwd(scratch)
dir.create("data/processed", recursive = TRUE)
dir.create("outputs", recursive = TRUE)

set.seed(20261111)
ids <- sprintf("synthetic_%03d", seq_len(27))
ratings <- rep(c(2.5, 6.5, 8.5), each = 9)
reviews <- data.frame(reviewid = ids, artist = paste0("Mock Artist ", seq_along(ids)),
                      wiki_wikipedia_title = paste0("Mock_Artist_", seq_along(ids)),
                      score = ratings, pub_date = as.character(as.Date("2018-04-01") + seq_along(ids) * 4),
                      genre = rep(c("Rock", "Hip-Hop", "Electronic"), length.out = length(ids)),
                      musicbrainz_release_to_review_days = rep(3:11, length.out = length(ids)))

panels <- lapply(seq_along(ids), function(i) {
  dd <- -56:56
  baseline <- 5 + i / 30
  shift <- ifelse(dd >= 0, 0.15 + 0.025 * ratings[i], 0)
  signal <- baseline + 0.001 * dd + 0.055 * sin(dd * pi / 3.5) + shift
  data.frame(reviewid = ids[i], event_day = dd,
             date = as.character(as.Date(reviews$pub_date[i]) + dd),
             views = round(expm1(signal)), observed = 1L)
})
panel <- do.call(rbind, panels)
utils::write.csv(reviews, "data/processed/attention_complete_sample.csv", row.names = FALSE)
utils::write.csv(panel, "data/processed/pageview_panel.csv", row.names = FALSE)

source("R/01_prepare.R")
ev <- read.csv("outputs/r/events_model_data.csv")
stopifnot(nrow(ev) == 27L, nrow(read.csv("outputs/r/pageview_event_daily.csv")) == 27L * 113L)
stopifnot(all(ev$short_delta > 0), all(ev$score %in% c(2.5, 6.5, 8.5)))
stopifnot(all(is.finite(ev$abnormal_increment)))

source("R/02_rq1_attention.R")
source("R/04_rq2_heterogeneity.R")
source("R/06_robustness.R")
source("R/05_matching.R")
source("R/07_figures.R")
stopifnot(file.exists("outputs/r/RQ1_sample_audit.csv"))
stopifnot(file.exists("outputs/r/RQ1_window_group_cluster_ci.csv"))
stopifnot(file.exists("outputs/r/RQ1_weekly_score_coefficients.csv"))
stopifnot(file.exists("outputs/r/RQ1_persistence_tests.csv"))
stopifnot(file.exists("outputs/r/RQ2_popularity_marginal_score_slopes.csv"))
stopifnot(file.exists("outputs/r/RQ2_distribution_by_popularity_score.csv"))
stopifnot(file.exists("outputs/r/figures/16_RQ1_event_time_cluster_CI.png"))
stopifnot(file.exists("outputs/r/figures/19_RQ2_marginal_score_effects.png"))
stopifnot(file.exists("outputs/r/RQ1_regressions.csv"))
stopifnot(file.exists("outputs/r/RQ2_heterogeneity.csv"))
stopifnot(file.exists("outputs/r/figures/02_event_time_attention.png"))
stopifnot(file.exists("outputs/r/figures/03_abnormal_attention.png"))
stopifnot(file.exists("outputs/r/figures/07_absolute_attention_by_popularity.png"))

# Optional Text-as-Data branch: numeric features and sampled comment days.
full_text <- data.frame(reviewid=ids, text_source="synthetic_fixture",
 text_sentiment_mean=(ratings-7)/20 + stats::rnorm(length(ids),sd=.03),
 text_sentiment_abs=runif(length(ids),.2,.6),
 text_negative_share=runif(length(ids),.1,.5),
 text_word_count=seq(650,by=10,length.out=length(ids)),
 text_innovation_rate_1000=runif(length(ids),0,8),
 text_controversy_rate_1000=runif(length(ids),0,8))
utils::write.csv(full_text,"data/processed/review_text_features.csv",row.names=FALSE)
youtube <- do.call(rbind,lapply(seq_along(ids),function(i) {
 data.frame(reviewid=ids[i],event_day=c(-2,0,3),
  comment_count=c(2,4,3),
  comment_sentiment_mean=c(.1,-.1,.4),
  comment_negative_share=c(.2,.6,.1))
}))
utils::write.csv(youtube,"data/processed/youtube_comment_daily.csv",row.names=FALSE)
source("R/09_text_analysis.R")
stopifnot(file.exists("outputs/r/TEXT_review_language_coverage.csv"))
stopifnot(file.exists("outputs/r/TEXT_review_language_regressions.csv"))
stopifnot(file.exists("outputs/r/TEXT_youtube_event_summary.csv"))
stopifnot(file.exists("outputs/r/figures/11_score_vs_expert_review_tone.png"))
stopifnot(file.exists("outputs/r/figures/13_audience_comment_tone.png"))
stopifnot(file.exists("outputs/r/figures/15_innovation_discourse_and_popularity.png"))

setwd(source_dir)
unlink(scratch, recursive = TRUE)
cat("PASS: R 113-day event assembly, regression, robustness and plots on SYNTHETIC fixtures\n")
