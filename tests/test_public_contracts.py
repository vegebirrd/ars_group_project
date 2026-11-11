"""GitHub CI tests do not require private/ignored user data."""
from pathlib import Path
import importlib.util
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
def load(relative):
    s=importlib.util.spec_from_file_location('check_module',ROOT/relative)
    m=importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m

def test_no_public_data_in_source_tree():
    s=load('scripts/check_before_publish.py')
    for x in ['data/unexpected/private_key.json', 'local_only/full_research_report.pdf','inputs/data/raw.csv','results/model.csv','reports/report.pdf']:
        assert s.forbidden(x)
    assert not s.forbidden('docs/RQ1_attention.md')
    assert not s.forbidden('src/run_analysis.py')

def test_wiki_manifest_113_day_boundaries():
    s=load('scripts/prepare_wiki_manifest.py')
    df=pd.DataFrame({'reviewid':['a'],'pub_date':['2018-05-15'],'wiki_wikipedia_title':['Example_Musician']})
    o=s.prepare(df)
    assert len(o)==1 and o.iloc[0].start=='2018032000' and o.iloc[0].end=='2018071000'

def test_wiki_url_encoding():
    s=load('scripts/fetch_wikimedia_pageviews.py')
    u=s.url_for('Björk','2018010100','2018040100')
    assert 'Bj%C3%B6rk' in u and '/all-access/user/' in u

def test_source_download_metadata():
    s=load('scripts/download_public_data.py')
    assert 'zenodo.org' in s.FILES['pitchfork']['url']
    assert 'githubusercontent.com' in s.FILES['spotify']['url']
    assert s.FILES['pitchfork']['md5']=='ef1de60923bc1ee13d946c6a05e54a0d'
