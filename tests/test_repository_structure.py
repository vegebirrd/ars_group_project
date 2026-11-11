"""Keep the public repository's entry points and docs in sync."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def test_main_r_modules_are_present():
    for i in range(1, 10):
        assert len(list((ROOT / 'R').glob(f'{i:02d}_*.R'))) == 1
    assert (ROOT/'R/helpers.R').exists()
    assert (ROOT/'run_r.R').exists()

def test_all_markdown_links_resolve_locally():
    for doc in ROOT.rglob('*.md'):
        if any(part.startswith('.') for part in doc.relative_to(ROOT).parts):
            continue
        for dest in re.findall(r'\[[^\]]+\]\(([^)]+)\)', doc.read_text(encoding='utf8')):
            if dest.startswith(('http:','https:','mailto:','#')):
                continue
            local = dest.split('#',1)[0]
            if local:
                assert (doc.parent / local).exists(), f'{doc}: {dest}'

def test_no_duplicate_historical_copy_and_no_large_inputs():
    assert not (ROOT/'src/replication').exists()
    assert (ROOT/'.gitignore').exists()
    ignore=(ROOT/'.gitignore').read_text()
    assert '/data/' in ignore and '/outputs/' in ignore and '*.zip' in ignore

def test_pipeline_has_stable_command_line_cohorts():
    cmd=(ROOT/'scripts/run_pipeline.py').read_text()
    assert "choices=['modern','historical']" in cmd
    assert "execute('prepare_extended_reviews.py'" in cmd
    assert "execute('build_event_panel.py')" in cmd
