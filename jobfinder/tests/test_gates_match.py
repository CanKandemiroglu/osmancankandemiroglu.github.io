from core.config import Config
from core.gates import run_gates, guess_country
from core.match import score_keyword, extract_requirements


def _p(title, body, country="", institution=""):
    return {"title": title, "body_text": body, "country": country, "institution": institution, "location": ""}


def test_gate3_postdoc_is_nogo(profile):
    g = run_gates(_p("Postdoctoral Researcher in zorbium", "You hold a PhD in chemistry.", "DE"), profile, Config(wisszeitvg_remaining_months=72))
    assert [x.status for x in g] == ["UNKNOWN", "PASS", "FAIL"]      # duration not stated -> WissZeitVG UNKNOWN


def test_gate3_phd_position_passes(profile):
    g = run_gates(_p("PhD position in zorbium spectroscopy", "3-year contract. MSc required.", "NL"), profile, Config(wisszeitvg_remaining_months=72))
    assert [x.status for x in g] == ["PASS", "PASS", "PASS"]


def test_gate1_unset_is_flagged_not_passed(profile):
    g = run_gates(_p("PhD position", "TV-L E13, 36 months, Kiel, Germany", "DE"), profile, Config())
    assert g[0].status == "UNKNOWN" and "unset" in g[0].reason


def test_gate1_fails_when_ad_longer_than_entitlement(profile):
    g = run_gates(_p("PhD position", "TV-L E13 for 4 years, Germany", "DE"), profile, Config(wisszeitvg_remaining_months=36))
    assert g[0].status == "FAIL"


def test_gate2_visa(profile):
    cfg = Config(wisszeitvg_remaining_months=72)
    assert run_gates(_p("PhD position", "Applicants must have the right to work in the US.", "US"), profile, cfg)[1].status == "FAIL"
    assert run_gates(_p("PhD position", "Visa sponsorship available.", "US"), profile, cfg)[1].status == "PASS"
    assert run_gates(_p("PhD position", "Nothing about visas.", "US"), profile, cfg)[1].status == "UNKNOWN"
    assert guess_country({"country": "", "location": "Kiel, Germany", "institution": "", "title": ""}) == "DE"


def test_gap_list_go(profile):
    body = ("Your profile\n- Hands-on experience with zorbium spectroscopy is required.\n"
            "- Experience with widget calibration.\n- Excellent English (desirable).\nWe offer\n- a salary")
    cfg = Config(wisszeitvg_remaining_months=72)
    r = score_keyword(_p("PhD position in zorbium", body, "NL"), profile, run_gates(_p("PhD position", body, "NL"), profile, cfg), cfg)
    assert r.verdict == "GO" and r.absent == []
    tiers = {x.text[:20]: x.tier for x in r.requirements}
    assert tiers["Hands-on experience "] == "HIS HANDS"


def test_gap_list_absent_listed_and_never_percentage(profile):
    body = ("Requirements\n- Proven experience in crocodile-free kraken taming is essential.\n"
            "- Knowledge of flux capacitor maintenance.\n")
    cfg = Config(wisszeitvg_remaining_months=72)
    r = score_keyword(_p("PhD position", body, "NL"), profile, run_gates(_p("PhD position", body, "NL"), profile, cfg), cfg)
    assert r.verdict == "STRETCH" and len(r.absent) == 1 and "kraken" in r.absent[0]
    assert "%" not in r.reason


def test_excluded_method_is_nogo(profile):
    body = "Requirements\n- Daily crocodile wrestling is essential.\n"
    cfg = Config(wisszeitvg_remaining_months=72)
    r = score_keyword(_p("PhD position", body, "NL"), profile, run_gates(_p("PhD position", body, "NL"), profile, cfg), cfg)
    assert r.verdict == "NO-GO" and "3c" in r.reason


def test_three_absent_is_nogo(profile):
    body = "Requirements\n- Experience in alpha welding required.\n- Experience in beta welding required.\n- Experience in gamma welding required.\n"
    cfg = Config(wisszeitvg_remaining_months=72)
    r = score_keyword(_p("PhD position", body, "NL"), profile, run_gates(_p("PhD position", body, "NL"), profile, cfg), cfg)
    assert r.verdict == "NO-GO" and len(r.absent) == 3


def test_generic_requirements_not_counted(profile):
    reqs = extract_requirements("Requirements\n- Excellent communication skills.\n- zorbium spectroscopy required.\n", Config().generic_requirements)
    assert [r.generic for r in reqs] == [True, False]
