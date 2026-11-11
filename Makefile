PYTHON ?= python3
.PHONY: install download data-analysis results test publish-check
install:
	$(PYTHON) -m pip install -r requirements.txt
	Rscript scripts/install_r_packages.R

download:
	$(PYTHON) scripts/run_pipeline.py --stage download

data-analysis:
	Rscript run_r.R --stage all

results:
	Rscript run_r.R --stage figures

test:
	$(PYTHON) -m pytest -q
	Rscript tests/test_r_pipeline.R

publish-check:
	$(PYTHON) scripts/check_before_publish.py --staged
