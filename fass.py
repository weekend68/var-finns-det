"""
Fass.se API helpers.

Stock checks go through the fass.se reverse-proxy:
  https://fass.se/api/content?endpoint=<url-encoded-cms-url>

Medication search and package lookup use apotekskoll.se's public API
(no authentication required) with local DB as fallback.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

FASS_REFERER = "https://fass.se/health/product/20011130000246/stock-status"
APOTEKSKOLL_BASE = "https://apotekskoll.se"
IN_STOCK_STATUSES = {"IN_STOCK", "FEW_IN_STOCK"}

# Simple in-memory search cache (query → (timestamp, results))
_search_cache: dict = {}
_CACHE_TTL = 300  # seconds


def _proxy_get(path):
    encoded = urllib.parse.quote(f"https://cms.fass.se/api/vard/{path}", safe="")
    req = urllib.request.Request(
        f"https://fass.se/api/content?endpoint={encoded}",
        headers={"Referer": FASS_REFERER},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _apotekskoll_get(path):
    req = urllib.request.Request(
        f"{APOTEKSKOLL_BASE}{path}",
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; medicinstatus/1.0)",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _proxy_post(path, body):
    encoded = urllib.parse.quote(f"https://cms.fass.se/api/vard/{path}", safe="")
    req = urllib.request.Request(
        f"https://fass.se/api/content?endpoint={encoded}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Referer": FASS_REFERER},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def search_medications(query):
    """
    Search for medications by name. Returns list of:
      {"npl_id": str, "name": str, "form": str}

    Primary: apotekskoll.se public API.
    Fallback: local DB (seeded medications).
    """
    q = query.strip()
    if not q or len(q) < 2:
        return []

    cached = _search_cache.get(q)
    if cached and (time.time() - cached[0]) < _CACHE_TTL:
        return cached[1]

    results = _apotekskoll_search(q)

    # Merge DB results so seeded medications always appear
    db_results = _db_search(q)
    seen_ids = {r["npl_id"] for r in results}
    for r in db_results:
        if r["npl_id"] not in seen_ids:
            results.append(r)
            seen_ids.add(r["npl_id"])

    _search_cache[q] = (time.time(), results)
    return results


def _apotekskoll_search(q):
    """Search medications via apotekskoll.se public API."""
    try:
        data = _apotekskoll_get(f"/api/search?q={urllib.parse.quote(q)}")
        hits = data.get("human-product-index", {}).get("hits", [])
        results = []
        for hit in hits[:15]:
            npl_id = hit.get("nplId", "")
            trade = hit.get("tradeName", "")
            strength = hit.get("strength", "")
            form = hit.get("doseForm", "")
            if not (npl_id and trade):
                continue
            name = f"{trade} {strength}".strip() if strength else trade
            results.append({"npl_id": str(npl_id), "name": name, "form": form})
        return results
    except Exception as e:
        print(f"  apotekskoll search error: {e}")
        return []


def _db_search(q):
    """Search seeded medications in local DB (case-insensitive LIKE)."""
    try:
        from db import get_db
        with get_db() as db:
            rows = db.execute(
                "SELECT npl_pack_id, name, strength, form FROM medications "
                "WHERE name LIKE ? ORDER BY name LIMIT 10",
                [f"%{q}%"],
            ).fetchall()
        return [
            {
                "npl_id": r["npl_pack_id"],
                "name": r["name"],
                "form": r["form"] or "",
            }
            for r in rows
        ]
    except Exception:
        return []


def get_packages(npl_id):
    """
    Get all available packagings for a medication (identified by nplId).
    Returns list of:
      {"npl_pack_id": str, "name": str, "strength": str, "form": str}

    Primary: apotekskoll.se public API.
    Fallback: Fass CMS proxy (often 404).
    """
    packages = _apotekskoll_packages(npl_id)
    if packages:
        return packages

    try:
        data = _proxy_get(f"product/{npl_id}/packages")
    except Exception as e:
        print(f"  fass packages error for {npl_id}: {e}")
        return []

    packages = []
    items = data if isinstance(data, list) else data.get("packages", data.get("items", []))
    for item in items:
        pack_id = (
            item.get("nplPackId") or item.get("npl_pack_id") or item.get("id") or ""
        )
        name = item.get("productName") or item.get("name") or ""
        strength = item.get("strength") or item.get("dose") or ""
        form = item.get("pharmaceuticalForm") or item.get("form") or ""
        if pack_id:
            packages.append({
                "npl_pack_id": str(pack_id),
                "name": name or f"{npl_id} – {strength}",
                "strength": strength,
                "form": form,
            })
    return packages


def _apotekskoll_packages(npl_id):
    """Get packages via apotekskoll.se public API."""
    try:
        data = _apotekskoll_get(f"/api/packages?nplId={urllib.parse.quote(npl_id)}")
        packages = []
        items = data if isinstance(data, list) else []
        for item in items:
            pack_id = item.get("nplPackId", "")
            packaging = item.get("packagingName", "")
            form = item.get("doseForm", "")
            if not pack_id:
                continue
            packages.append({
                "npl_pack_id": str(pack_id),
                "name": packaging or form or pack_id,
                "strength": "",
                "form": form,
            })
        return packages
    except Exception as e:
        print(f"  apotekskoll packages error for {npl_id}: {e}")
        return []


def check_stock(npl_pack_id, gln_codes, pharmacy_map):
    """
    Check stock for nplPackId across a list of GLN codes.
    Returns list of in-stock pharmacies:
      {"name": str, "address": str, "status": str, "exchangeable": bool}

    Batches GLN codes in groups of 50; retries 400s in sub-batches of 10
    (LMV has pharmacies that Fass doesn't recognize).
    """
    results = []
    for i in range(0, len(gln_codes), 50):
        batch = gln_codes[i:i + 50]
        try:
            data = _proxy_post(f"pharmacy/stock/{npl_pack_id}", batch)
            results.extend(data)
        except Exception as e:
            if getattr(e, "code", None) == 400:
                for j in range(0, len(batch), 10):
                    sub = batch[j:j + 10]
                    try:
                        results.extend(_proxy_post(f"pharmacy/stock/{npl_pack_id}", sub))
                    except Exception:
                        pass
                    time.sleep(0.1)
            else:
                print(f"  Fass batchfel (offset {i}): {e}")
        time.sleep(0.2)

    in_stock = []
    for r in results:
        if r.get("stockInformation") in IN_STOCK_STATUSES:
            ph = pharmacy_map.get(r["glnCode"], {})
            in_stock.append({
                "name": ph.get("name", r["glnCode"]),
                "address": ph.get("address", ""),
                "status": r["stockInformation"],
                "exchangeable": r.get("exchangeableProductInStock", False),
            })
    return in_stock
