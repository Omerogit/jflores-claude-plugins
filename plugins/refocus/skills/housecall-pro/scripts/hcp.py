# -*- coding: utf-8 -*-
"""hcp.py - read the company's Housecall Pro from this computer, through the J Flores Brain door.

Omero, 2026-10-02: "they need to be able to ask questions and not get 'I am not connected to a Housecall Pro yet'...
Cookie jar should be baked in, and they should ask anything of Housecall Pro." This computer holds no HCP login and
no key: the door checks this desk's Brain key, and the server reads HCP with the house's own session (the cookie
jar) or the public API, READ ONLY, and hands the answer back.

    hcp.py customers "Garza"                 find customers by name, phone (10 digits), email or address words
    hcp.py customer cus_...                  one customer: phones, email, addresses, tags, notes
    hcp.py jobs --customer cus_...           that customer's jobs, newest first
    hcp.py job 12109                         a job by its number (or job_...): job, line items with part numbers
    hcp.py schedule 2026-10-03 [--to DATE]   jobs scheduled that day (or range), by start time
    hcp.py audit job_...                     who changed the job, and when (the audit line)
    hcp.py plan cus_...                      the customer's membership / service agreements
    hcp.py estimates --customer cus_...      that customer's estimates
    hcp.py invoices --customer cus_...       that customer's invoices
    hcp.py get web|api PATH [k=v ...]        any other read: web = the app's own calls (/alpha/ /api/ /pro/),
                                             api = the public API (api.housecallpro.com)
    hcp.py grid jobs|invoices|estimates --filter '{"logic":"and","filters":[...]}'   the app's grid lookups

Prints JSON. Standard library only. Exit codes: 3 no brain connected - 5 refused - 6 the server did not answer -
7 the house's HCP session is being refreshed (try again in a minute).
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
D = os.environ.get("REFOCUS_HOME") or os.path.join(HOME, ".claude", "refocus")   # REFOCUS_HOME: tests only
CONF = os.path.join(D, "door.json")
MAX_OUT = 60000


def out(s=""):
    sys.stdout.write(s + "\n")
    sys.stdout.flush()


def conf():
    try:
        with open(CONF, encoding="utf-8-sig") as f:
            c = json.load(f)
        if c.get("door") and c.get("key"):
            return c
    except (OSError, ValueError):
        pass
    out("NO BRAIN CONNECTED on this computer, so Housecall Pro cannot be read from here yet. The person needs their")
    out("Brain link from Omero (paste it and say 'connect my brain'). Housecall Pro comes with it.")
    sys.exit(3)


def read(door, path, params=None, method="GET", body=None):
    c = conf()
    req = {"door": door, "method": method, "path": path, "params": [[k, str(v)] for k, v in (params or [])]}
    if body is not None:
        req["body"] = body
    h = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "refocus-plugin/hcp-1.0",
         "Authorization": "Bearer " + c["key"]}
    r = urllib.request.Request(c["door"] + "/v1/hcp", data=json.dumps(req).encode("utf-8"), method="POST", headers=h)
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            res = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8") or "{}").get("error")
        except ValueError:
            err = None
        if e.code == 503:
            out("Housecall Pro is not answering right now: %s" % (err or "try again in a minute"))
            sys.exit(7)
        out("Refused: %s" % (err or "HTTP %d" % e.code))
        sys.exit(5)
    except Exception as e:
        out("The server did not answer (%s). Try again in a minute." % type(e).__name__)
        sys.exit(6)
    if not res.get("ok"):
        out("Housecall Pro answered HTTP %s for %s: %s" % (res.get("status"), path,
                                                         json.dumps(res.get("data"), ensure_ascii=False)[:600]))
        sys.exit(5)
    return res.get("data")


def show(obj):
    s = json.dumps(obj, ensure_ascii=False, indent=1)
    if len(s) > MAX_OUT:
        s = s[:MAX_OUT] + "\n... (cut at %d characters; ask for less: a smaller page_size, or one record)" % MAX_OUT
    out(s)


def pick(d, keys):
    return {k: d.get(k) for k in keys if d.get(k) not in (None, "", [], {})}


def customers(text, n):
    q = re.sub(r"\D", "", text) if re.fullmatch(r"[\d\s().+-]{10,}", text.strip()) else text
    q = q[-10:] if q.isdigit() else q                  # HCP finds a phone by its bare 10 digits; +1... finds nothing
    d = read("web", "/alpha/customers", [("q", q), ("page_size", n)])
    rows = [pick(r, ("id", "display_name", "first_name", "last_name", "company", "mobile_number", "home_number",
                     "work_number", "email", "tags", "notes", "created_at")) for r in (d or {}).get("data") or []]
    show({"found": (d or {}).get("total_count"), "shown": len(rows), "customers": rows})


def find_job(ref):
    if ref.startswith("job_"):
        return ref
    num = ref.lstrip("#")
    g = read("web", "/pro/grid/jobs_for_grid", method="POST", body={
        "filter": {"logic": "and", "filters": [{"field": "display_invoice_number", "operator": "eq", "value": num}]},
        "page": 1, "pageSize": 5, "skip": 0, "take": 5, "sort": []})
    rows = (g or {}).get("results") or []
    if not rows:
        out("No job numbered %s in Housecall Pro." % num)
        sys.exit(0)
    return rows[0].get("uuid") or rows[0].get("id")


def job(ref):
    jid = find_job(ref)
    j = read("api", "/jobs/%s" % jid)
    li = read("web", "/alpha/jobs/%s/line_items" % jid, [("expand[]", "material_line_item_detail")])
    lines = []
    for x in (li or {}).get("data") or []:
        m = x.get("material_detail") or x.get("material_line_item_detail") or {}   # the answer nests it under .data
        m = (m.get("data") or m) if isinstance(m, dict) else {}
        row = pick(x, ("name", "description", "kind", "quantity", "unit_price", "amount"))
        row.update(pick(m, ("part_number", "material_vendor_uuid", "material_purchase_status_uuid",
                            "material_source_uuid")))
        lines.append(row)
    show({"job": j, "line_items": lines})


def schedule(start, end, n):
    """The public API will not sort by start time (HTTP 400), so read the day's pages and sort here."""
    jobs, page = [], 1
    while len(jobs) < n:
        d = read("api", "/jobs", [("scheduled_start_min", start + "T00:00:00"), ("scheduled_start_max", end + "T23:59:59"),
                                  ("page_size", 100), ("page", page)]) or {}
        jobs += d.get("jobs") or []
        if page >= (d.get("total_pages") or 1):
            break
        page += 1
    jobs.sort(key=lambda j: ((j.get("schedule") or {}).get("scheduled_start") or ""))
    show({"scheduled": len(jobs), "jobs": jobs[:n]})


def invoices(cid, n):
    """/invoices IGNORES customer_id (every invoice comes back), so go through the customer's jobs, which filter."""
    d = read("api", "/jobs", [("customer_id", cid), ("page_size", min(n, 50)), ("sort_direction", "desc")]) or {}
    out_ = []
    for j in (d.get("jobs") or [])[:n]:
        inv = read("api", "/jobs/%s/invoices" % j["id"]) or {}
        for i in inv.get("invoices") or (inv if isinstance(inv, list) else []):
            out_.append(dict(i, job_number=j.get("invoice_number")))
    show({"jobs_checked": len((d.get("jobs") or [])[:n]), "invoices": out_})


def main():
    ap = argparse.ArgumentParser(description="Read Housecall Pro through the J Flores Brain door (read only).")
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("customers"); a.add_argument("text"); a.add_argument("--n", type=int, default=25)
    a = sp.add_parser("customer"); a.add_argument("id")
    a = sp.add_parser("jobs"); a.add_argument("--customer", required=True); a.add_argument("--n", type=int, default=25)
    a = sp.add_parser("job"); a.add_argument("ref")
    a = sp.add_parser("schedule"); a.add_argument("date"); a.add_argument("--to"); a.add_argument("--n", type=int, default=100)
    a = sp.add_parser("audit"); a.add_argument("ref")
    a = sp.add_parser("plan"); a.add_argument("id")
    for name in ("estimates", "invoices"):
        a = sp.add_parser(name); a.add_argument("--customer", required=True); a.add_argument("--n", type=int, default=25)
    a = sp.add_parser("get"); a.add_argument("door", choices=("web", "api")); a.add_argument("path")
    a.add_argument("params", nargs="*", help="name=value")
    a = sp.add_parser("grid"); a.add_argument("what", choices=("jobs", "invoices", "estimates"))
    a.add_argument("--filter", required=True); a.add_argument("--n", type=int, default=25)
    o = ap.parse_args()

    if o.cmd == "customers":
        customers(o.text, o.n)
    elif o.cmd == "customer":
        show(read("api", "/customers/%s" % o.id))
    elif o.cmd == "jobs":
        show(read("api", "/jobs", [("customer_id", o.customer), ("page_size", o.n), ("sort_direction", "desc")]))
    elif o.cmd == "job":
        job(o.ref)
    elif o.cmd == "schedule":
        schedule(o.date, o.to or o.date, o.n)
    elif o.cmd == "audit":
        d = read("web", "/api/jobs/%s/activity_events" % find_job(o.ref), [("page_size", 100)])
        rows = [pick(r, ("id", "who", "kind", "when", "message")) for r in (d or {}).get("data") or []]
        show({"changes": (d or {}).get("total_count"), "oldest_first": sorted(rows, key=lambda r: r.get("id") or 0),
              "note": "'when' is local time wearing a false Z; the order is by id"})
    elif o.cmd == "plan":
        show(read("web", "/alpha/customer_service_agreements", [("customer_id", o.id)]))
    elif o.cmd == "estimates":
        show(read("api", "/estimates", [("customer_id", o.customer), ("page_size", o.n)]))
    elif o.cmd == "invoices":
        invoices(o.customer, o.n)
    elif o.cmd == "get":
        params = []
        for p in o.params:
            if "=" not in p:
                out("each param is name=value: %r" % p)
                sys.exit(2)
            params.append(tuple(p.split("=", 1)))
        show(read(o.door, o.path, params))
    elif o.cmd == "grid":
        try:
            flt = json.loads(o.filter)
        except ValueError:
            out("--filter is JSON, like {\"logic\":\"and\",\"filters\":[{\"field\":\"display_invoice_number\","
                "\"operator\":\"eq\",\"value\":\"12109\"}]}")
            sys.exit(2)
        show(read("web", "/pro/grid/%s_for_grid" % o.what, method="POST",
                  body={"filter": flt, "page": 1, "pageSize": o.n, "skip": 0, "take": o.n, "sort": []}))


if __name__ == "__main__":
    main()
