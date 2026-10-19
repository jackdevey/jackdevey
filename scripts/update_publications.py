#!/usr/bin/env python3
import json
import os
import re
import sys
import urllib.request

ORCID = os.environ.get("ORCID_ID", "0009-0002-9513-2817")
HIGHLIGHT = os.environ.get("HIGHLIGHT_NAME", "Devey J")
README = os.environ.get("README_PATH", "README.md")
MAX_ENTRIES = int(os.environ.get("MAX_ENTRIES", "5"))
START, END = "<!-- PUBLICATIONS:START -->", "<!-- PUBLICATIONS:END -->"
UA = "readme-update-publications (mailto:jack@jw3.uk)"  # polite-pool header


def get_json(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def orcid_dois(orcid):
    data = get_json(f"https://pub.orcid.org/v3.0/{orcid}/works")
    dois = []
    for group in data.get("group", []):
        for eid in group.get("external-ids", {}).get("external-id", []):
            if eid.get("external-id-type") == "doi":
                dois.append(eid["external-id-value"].lower().strip())
                break  # one DOI per grouped work (ORCID dedupes duplicates into groups)
    return list(dict.fromkeys(dois))


def initials(given):
    parts = re.split(r"[\s\-\.]+", given or "")
    return "".join(p[0].upper() for p in parts if p)


def fmt_author(a):
    if "family" in a:
        return f"{a['family']} {initials(a.get('given', ''))}".strip()
    return a.get("literal", "")


def fmt_entry(m):
    authors = ", ".join(fmt_author(a) for a in m.get("author", []))
    authors = authors.replace(HIGHLIGHT, f"**{HIGHLIGHT}**")
    title = (m.get("title") or "").rstrip(".")
    venue = m.get("container-title") or m.get("event", {}).get("name", "")
    if isinstance(venue, list):
        venue = venue[0] if venue else ""
    year = (m.get("issued") or m.get("published") or {}).get("date-parts", [[None]])[0][0]

    tail = str(year or "n.d.")
    if m.get("volume"):
        tail += f"; {m['volume']}"
        if m.get("issue"):
            tail += f"({m['issue']})"
        if m.get("page") or m.get("article-number"):
            tail += f":{m.get('page') or m.get('article-number')}"
    elif m.get("page"):
        tail += f"; pp. {m['page'].replace('-', '–')}"

    doi = m.get("DOI", "")
    return year or 0, f"- {authors}. {title}. {venue}. {tail}. <https://doi.org/{doi}>"


def main():
    entries = []
    for doi in orcid_dois(ORCID):
        try:
            meta = get_json(f"https://doi.org/{doi}", "application/vnd.citationstyles.csl+json")
            entries.append(fmt_entry(meta))
        except Exception as e:  # don't let one bad DOI wipe the section
            print(f"warning: skipped {doi}: {e}", file=sys.stderr)

    if not entries:
        sys.exit("No publications resolved; leaving README untouched.")

    entries.sort(key=lambda e: e[0], reverse=True)
    block = "\n".join(e[1] for e in entries[:MAX_ENTRIES])
    if len(entries) > MAX_ENTRIES:
        block += f"\n\n[Full list on ORCID](https://orcid.org/{ORCID})"

    with open(README, encoding="utf-8") as f:
        text = f.read()
    if START not in text or END not in text:
        sys.exit(f"Markers {START} / {END} not found in {README}.")

    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        f"{START}\n{block}\n{END}",
        text,
        flags=re.S,
    )
    if new != text:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new)
        print(f"Updated {len(entries)} publications.")
    else:
        print("No changes.")


if __name__ == "__main__":
    main()
