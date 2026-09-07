"""KU Leuven jobsite. Verified 2026-09-07.

The listing page is rendered client-side. Its own source declares
  filter_component_api_base_url = "https://icts-p-fii-toep-component-filter2.cloud.icts.kuleuven.be"
and mounts <filter-component v-bind="{'project_name':'Jobsite_academic','project_environment':'production'}">.
Its app.js POSTs to {base}/api/projects/{project_name}/search with {_locale, environment, release}
and receives {hits:[{_id, _source:{posting:{title,teaser}, applyBefore, city, orgUnitDescription}}],
total_nb_hits, page}. We read base URL and project name from the page and call that endpoint.
The per-posting URL is not present in the response, so url = the listing page (confirmed) and the
hit id is kept in external_id for the user to search on the page.
"""
from __future__ import annotations
import json
import re
from adapters.base import Posting, AdapterError
from core.util import parse_date, clean_text


def list_postings(source, fetcher, config):
    page = fetcher.get(source["url"])
    if not page.ok:
        raise AdapterError(f"listing page fetch failed: status={page.status} error={page.error}")
    mb = re.search(r'filter_component_api_base_url\s*=\s*"([^"]+)"', page.text)
    mp = re.search(r"'project_name'\s*:\s*'([^']+)'", page.text)
    me = re.search(r"'project_environment'\s*:\s*'([^']+)'", page.text)
    if not (mb and mp):
        raise AdapterError("page no longer declares filter_component_api_base_url / project_name")
    base, project, env = mb.group(1).rstrip("/"), mp.group(1), (me.group(1) if me else "production")
    lang = "en" if "lang=en" in source["url"] else "nl"
    out, ids = [], set()
    for pg in range(config.max_pages):
        u = f"{base}/api/projects/{project}/search" + (f"?page={pg}" if pg else "")
        res = fetcher.post(u, json={"_locale": lang, "environment": env, "release": ""})
        if not res.ok:
            if pg == 0:
                raise AdapterError(f"search endpoint failed: status={res.status} error={res.error}")
            break
        try:
            data = json.loads(res.text)
        except json.JSONDecodeError:
            raise AdapterError("search endpoint returned non-JSON")
        hits = data.get("hits") or []
        if not hits:
            break
        for h in hits:
            src = h.get("_source", {})
            hid = str(h.get("_id") or src.get("id") or "")
            if not hid or hid in ids:
                continue
            ids.add(hid)
            post = src.get("posting", {})
            out.append(Posting(external_id=hid, title=clean_text(post.get("title", "")),
                               institution="KU Leuven - " + clean_text(src.get("orgUnitDescription", "")),
                               location=clean_text(src.get("city", "")), url=source["url"],
                               deadline=parse_date(str(src.get("applyBefore", ""))),
                               body_text=clean_text(post.get("teaser", "")), country="BE",
                               extra={"occupation": src.get("occupation", "")}))
        total = data.get("total_nb_hits") or 0
        if len(ids) >= total:
            break
    return out
