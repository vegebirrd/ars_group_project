# Selected references, API documentation and source provenance

## Research methods and mechanisms

1. Berger, J., Sorensen, A. T., & Rasmussen, S. J. (2010). *Positive Effects of Negative Publicity: When Negative Reviews Increase Sales.* **Marketing Science**, 29(5), 815–827. https://doi.org/10.1287/mksc.1090.0557. Prior awareness may moderate responses to negative publicity.
2. Hendricks, K., & Sorensen, A. (2009). *Information and the Skewness of Music Sales.* **Journal of Political Economy**, 117(2), 324–369. https://doi.org/10.1086/599283. Music release/learning dynamics can affect sales, confounding review event dates.
3. Lind, J. T., & Mehlum, H. (2010). *With or Without U? The Appropriate Test for a U-Shaped Relationship.* **Oxford Bulletin of Economics and Statistics**, 72(1), 109–118. https://doi.org/10.1111/j.1468-0084.2009.00569.x.
4. Cameron, A. C., & Miller, D. L. (2015). *A Practitioner’s Guide to Cluster-Robust Inference.* **Journal of Human Resources**, 50(2), 317–372. https://doi.org/10.3368/jhr.50.2.317.
5. Pinter, A. T., Paul, J. M., Smith, J., & Brubaker, J. R. (2020). *P4KxSpotify: A Dataset of Pitchfork Music Reviews and Spotify Musical Features.* **ICWSM**. https://doi.org/10.1609/icwsm.v14i1.7355.

## Primary public datasets and API manuals (verified 2026-11-11)

6. Zenodo P4KxSpotify record: https://zenodo.org/records/3603330 (file `output-data.csv`, source lists 18,403 music reviews).
7. Spotify Global Weekly Top 200 historical community archive: https://github.com/younver/spotify-top-200-dataset. Schema describes `week`, `streams`, `album_id`, `artist_id`, and multiple collaborator rows.
8. Wikimedia Analytics API, page view endpoints: https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html; getting started https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/getting-started.html. Historical pageviews start 2015-07-01.
9. MusicBrainz API: https://musicbrainz.org/doc/MusicBrainz_API and rate limits https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting (identify client; ~1 req/sec).
10. Luminate CONNECT Charts: https://support.luminatedata.com/portal/en/kb/articles/charts. Weekly and historical product sales chart components; account/licensing required.
11. Luminate Methodology FAQs: https://support.luminatedata.com/portal/en/kb/articles/methodology-faqs. Historical availability and distinctions between units and equivalents.
12. Google Trends API Alpha: https://developers.google.com/search/apis/trends (rolling 5-year history; does not reach 2018–2019 as of 2026).
13. GDELT Project historical archive: https://www.gdeltproject.org/ and https://data.gdeltproject.org/gdeltv2/masterfilelist.txt.
14. UK Official Charts archive guide: https://www.officialcharts.com/who-we-are/how-to-search-our-database/.
15. Billboard 200: https://www.billboard.com/charts/billboard-200/.

## Internal, user-supplied project sources

- `TODO_ARS_Group_Project.pdf`: the research objectives and TODO list (not distributed on GitHub).
- `preanalysis_report.pdf`: 2015–2017 reference report (not distributed on GitHub).
- `preanalysis_report_v2.pdf`: 2018–2019 data extension, preanalysis, and chart-match reference (not distributed on GitHub).
- `local_only/original_user_data.zip`: uploaded project data and raw-source cache (not distributed on GitHub).
- `local_only/full_research_report.pdf`: verified, user-requested single-PDF publication draft with local embedded data/code (not distributed on GitHub).

When writing a formal paper, cite dataset authors, source providers and methods papers separately. PDF reports/summary figures in this repository are research artifacts and not substitutes for original academic literature.

## Text-as-Data / audience-reaction extension (November 2026)

16. Gentzkow, M., Kelly, B., & Taddy, M. (2019). *Text as Data*. **Journal of Economic Literature**, 57(3), 535–574. https://doi.org/10.1257/jel.20181020
17. Chevalier, J. A., & Mayzlin, D. (2006). *The Effect of Word of Mouth on Sales: Online Book Reviews*. **Journal of Marketing Research**, 43(3), 345–354. https://doi.org/10.1509/jmkr.43.3.345
18. Kozlowski, A. C., Taddy, M., & Evans, J. A. (2019). *The Geometry of Culture: Analyzing the Meanings of Class through Word Embeddings*. **American Sociological Review**, 84(5), 905–949. https://doi.org/10.1177/0003122419877135
19. *Using word embedding models to capture changing media discourses: a study on the role of legitimacy, gender and genre in 24,000 music reviews, 1999–2021*. **Journal of Computational Social Science** (2022). https://doi.org/10.1007/s42001-022-00182-8
20. Full review text optional source: https://huggingface.co/datasets/mattismegevand/pitchfork (separate from P4KxSpotify; read source reuse terms).
21. YouTube Data API commentThreads.list: https://developers.google.com/youtube/data/reference/rest/v3/commentThreads/list.
22. Academic access to Reddit data: https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data.
