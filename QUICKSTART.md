# Running ars_group_project

R runs in Terminal or VS Code; RStudio is not required. On macOS:

```bash
brew install r
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
Rscript scripts/install_r_packages.R
```

## 1. Choose a data route

**Modern 2020–2025** (downloads data, requires internet):

```bash
python scripts/run_pipeline.py --cohort modern --stage all --email you@university.edu
```

Or execute one stage at a time with `--stage download|prepare|match|wikipedia|popularity|charts|audit`.

**Historical 2018–2019** (existing local archive):

```bash
python scripts/import_project_archive.py --archive ~/Downloads/data.zip --period 2018-2019
```

Historical data can also be collected using `python scripts/run_pipeline.py --cohort historical --stage all --email you@university.edu`.

## 2. Analyze

```bash
Rscript run_r.R --stage all          # all RQs and figures
Rscript run_r.R --stage attention    # RQ1, RQ2, matching, robustness
Rscript run_r.R --stage consumption  # chart outcomes
Rscript run_r.R --stage figures      # redraw figures from prepared results
Rscript run_r.R --stage text         # optional text measures
```

Intermediate files: `data/processed/`. Results: `outputs/r/` and `outputs/r/figures/`. The main paper template is `reports/ars_research_report.qmd` (render with `quarto render reports/ars_research_report.qmd`).

## 3. Verify

```bash
python -m pytest -q
python scripts/verify_r_estimands.py   # after R stage prepare
Rscript tests/test_r_pipeline.R
```

For GitHub: `git add .` followed by `python scripts/check_before_publish.py --staged`. The `.gitignore` excludes local datasets, downloads, API caches and generated figures.
