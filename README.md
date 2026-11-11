# ars_group_project

**The Tinashe Effect or the Tyga Effect?**  
*Music Criticism, Audience Attention, and Cultural Gatekeeping*

A social-science study of how professional music criticism relates to public attention, music consumption and the distribution of cultural visibility. Python collects and links data; R estimates the empirical models and produces figures.

## Research questions

**RQ1 · Criticism and attention.** How do review valence and extremity relate to the size and persistence of public attention? Do comparable patterns appear in historical chart visibility?

**RQ2 · Cultural gatekeeping.** Do less-known artists gain proportionally more attention, or do established artists capture larger absolute gains? How do prior recognition and genre shape these relationships?

The main extension covers **2020–2025**. The **2015–2019** data provide historical replication. The text-analysis module studies professional-review language and audience discussion as complementary evidence.

## Get started

Requires Python 3.11+ and R. RStudio is optional.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
Rscript scripts/install_r_packages.R
```

Download the modern review sample, resolve identities and collect historical attention / chart data:

```bash
python scripts/run_pipeline.py --cohort modern --stage all --email you@university.edu
Rscript run_r.R --stage all
```

For a quick first pass, run only the review download and cleaning stages:

```bash
python scripts/run_pipeline.py --stage download
python scripts/run_pipeline.py --stage prepare
```

If you already have the 2018–2019 research archive, import it and run R without making API requests:

```bash
python scripts/import_project_archive.py --archive ~/Downloads/data.zip --period 2018-2019
Rscript run_r.R --stage all
```

Results are written to `outputs/r/` (tables) and `outputs/r/figures/`. All data and generated results remain local and are excluded from Git.

## Repository

| Directory | Purpose |
|---|---|
| `R/` | RQ1, RQ2, matching, timing checks, charts and figures |
| `scripts/` | Downloads, matching, data assembly and command-line entry points |
| `src/` | Python data transformations and independent cross-checks |
| `docs/` | Research design, data sources, models and result interpretation |
| `reports/` | Quarto research-paper template |
| `tests/` | Data-contract and synthetic-data tests |
| `data/`, `outputs/` | Local research data and generated outputs (Git-ignored) |

## Main specification

With \(x_i = score_i - 7\), baseline log views \(B_i\), and prior weekly trend \(T_i\):

\[
\Delta_i^{0:6} = \alpha + \beta x_i + \gamma B_i + \eta T_i + \mu_{year(i)} + \varepsilon_i.
\]

Inference is clustered by artist Wikipedia page. We estimate adjacent-week changes, longer-run attention, nonlinearity and release-date-adjusted variants. RQ2 adds interactions between score and **pre-review** visibility, measured using Wikipedia history, earlier Pitchfork coverage and historical music charts. The chart analysis examines observable Top 200/Top 100 participation rather than recorded album-unit sales.

## Reading guide

- [Research questions and hypotheses](docs/RESEARCH.md)
- [Models and identification](docs/METHODS.md)
- [Data sources, schema and collection](docs/DATA.md)
- [Results and figure index](docs/OUTPUTS.md)
- [Text-as-Data module](docs/TEXT_AS_DATA.md)
- [References](docs/REFERENCES.md)
- [Terminal / VS Code workflow](QUICKSTART.md)
