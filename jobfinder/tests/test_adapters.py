from datetime import date
from conftest import FakeFetcher
from adapters import peopleadmin, unige_wdportal, euraxess, kuleuven, csic_sede, rss, stubs, get_adapter
import pytest


def test_peopleadmin_uri(cfg):
    f = FakeFetcher({"https://jobs.uri.edu/postings/search": "uri_search.html", "https://jobs.uri.edu/": "uri_root.html"})
    ps = peopleadmin.list_postings({"url": "https://jobs.uri.edu/", "name": "URI"}, f, cfg)
    assert len(ps) == 30
    p = ps[0]
    assert p.external_id == "17038" and p.url == "https://jobs.uri.edu/postings/17038"
    assert p.title.startswith("Housekeeper") and p.institution == "Dining Central Operations"
    assert p.posted_date == date(2026, 9, 4) and p.deadline == date(2026, 9, 13)


def test_unige(cfg):
    f = FakeFetcher({"https://jobs.unige.ch/www/wd_portal.search_results": "unige_results.html",
                     "https://jobs.unige.ch/www/wd_portal.search_start": "unige_search_start.html",
                     "https://jobs.unige.ch/": "unige_root.html"})
    ps = unige_wdportal.list_postings({"url": "https://jobs.unige.ch/", "name": "UNIGE"}, f, cfg)
    assert ps, "no postings parsed"
    p = next(x for x in ps if x.external_id == "75611")
    assert "littérature italienne" in p.title and p.deadline == date(2026, 10, 31)
    assert p.url.startswith("https://jobs.unige.ch/www/wd_portal.show_job?")
    assert p.extra["ref"] == "7051"


def test_euraxess(cfg):
    f = FakeFetcher({"https://euraxess.ec.europa.eu/jobs/search": "euraxess_search.html"})
    ps = euraxess.list_postings({"url": "https://euraxess.ec.europa.eu/jobs/search"}, f, cfg)
    assert len(ps) == 10
    p = ps[1]
    assert p.external_id == "464069" and p.title.startswith("PhD Position in Cognitive Neuroscience")
    assert p.institution == "University of Caen Normandie" and p.posted_date == date(2026, 9, 7)
    assert p.country == "France"


def test_kuleuven(cfg):
    f = FakeFetcher({"https://www.kuleuven.be/personeel/jobsite/jobs/staff": "kuleuven_staff.html",
                     "https://icts-p-fii-toep-component-filter2.cloud.icts.kuleuven.be/api/projects/Jobsite_academic/search": "kuleuven_search.json"})
    src = {"url": "https://www.kuleuven.be/personeel/jobsite/jobs/staff?lang=en"}
    ps = kuleuven.list_postings(src, f, cfg)
    assert len(ps) == 15 and f.calls[1][0] == "POST"
    p = ps[0]
    assert p.external_id == "60737602" and "PhD researcher" in p.title and p.deadline == date(2026, 9, 30)
    assert p.url == src["url"]           # no per-posting URL is exposed; we never construct one


def test_csic(cfg):
    f = FakeFetcher({"https://sede.csic.gob.es/tramites/convocatorias-de-personal": "csic_listing.html"})
    ps = csic_sede.list_postings({"url": "https://sede.csic.gob.es/tramites/convocatorias-de-personal"}, f, cfg)
    assert len(ps) >= 3
    p = ps[0]
    assert p.external_id == "38224" and p.title == "Contratos predoctorales IPNA-CSIC"
    assert p.url == "https://sede.csic.gob.es/tramites/convocatorias-de-personal/convocatoria/38224"


@pytest.mark.parametrize("fname,url,n", [("egu_bg.rss", "https://www.egu.eu/bg/jobs/rss/", 10),
                                         ("agu.rss", "https://findajob.agu.org/jobsrss/?countrycode=US", 20),
                                         ("icman_empleo.rss", "https://www.icman.csic.es/tag/empleo/feed/", 1)])
def test_rss(cfg, fname, url, n):
    f = FakeFetcher({url: fname})
    ps = rss.list_postings({"url": url, "country": "XX"}, f, cfg)
    assert len(ps) == n and all(p.url.startswith("http") and p.title for p in ps)


def test_egu_rss_title_split(cfg):
    f = FakeFetcher({"https://www.egu.eu/bg/jobs/rss/": "egu_bg.rss"})
    p = rss.list_postings({"url": "https://www.egu.eu/bg/jobs/rss/", "country": ""}, f, cfg)[0]
    assert p.title == "Senior Water Data Scientist" and p.location == "United States of America"
    assert p.posted_date == date(2026, 9, 4)


def test_stubs_raise(cfg):
    for plat in ["workday", "jobbnorge", "successfactors", "varbi", "cnrs", "pageup", "reachmee",
                 "oracle_hcm", "uc_recruit", "taleo", "emply", "valtiolle", "starfatorg", "szn_joomla"]:
        with pytest.raises(NotImplementedError):
            get_adapter(plat).list_postings({"platform": plat, "url": "https://example.invalid/"}, None, cfg)
