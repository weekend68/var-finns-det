import os

from flask import Blueprint, redirect, render_template, request, url_for

import fass
from db import get_db

bp = Blueprint("manage", __name__)
SITE_URL = os.getenv("SITE_URL", "").rstrip("/")


def _get_subscriber(db, token):
    return db.execute(
        "SELECT t.subscriber_id, sub.email "
        "FROM tokens t JOIN subscribers sub ON t.subscriber_id=sub.id "
        "WHERE t.token=? AND t.type='manage' AND t.used_at IS NULL AND t.expires_at > datetime('now')",
        [token],
    ).fetchone()


@bp.route("/manage/<token>")
def manage(token):
    with get_db() as db:
        auth = _get_subscriber(db, token)
        if not auth:
            return render_template("message.html",
                title="Ogiltig länk",
                message="Länken hittades inte eller har gått ut.",
                icon="❌"), 404

        subs = db.execute(
            "SELECT s.id, s.npl_pack_id, s.expires_at, s.last_notified_at, s.active, m.name "
            "FROM subscriptions s JOIN medications m ON s.npl_pack_id=m.npl_pack_id "
            "WHERE s.subscriber_id=? AND s.active=1 ORDER BY s.created_at",
            [auth["subscriber_id"]],
        ).fetchall()

    subscriptions = [dict(s) for s in subs]

    # Retroactively fix any subscription where name=npl_pack_id (placeholder from before fix)
    for s in subscriptions:
        if s["name"] == s["npl_pack_id"]:
            real_name = _lookup_name(s["npl_pack_id"])
            if real_name:
                try:
                    with get_db() as db:
                        db.execute(
                            "UPDATE medications SET name=? WHERE npl_pack_id=? AND name=?",
                            [real_name, s["npl_pack_id"], s["npl_pack_id"]],
                        )
                        db.commit()
                except Exception:
                    pass
                s["name"] = real_name

    return render_template("manage.html",
        token=token,
        email=auth["email"],
        subscriptions=subscriptions,
        site_url=SITE_URL,
    )


def _lookup_name(npl_pack_id):
    """Try to find the real medication name for a npl_pack_id via Fass search."""
    try:
        # Strategy 1: search by the npl_pack_id directly (works if Fass indexes by ID)
        results = fass._fass_search(npl_pack_id)
        if results:
            return results[0]["name"]
    except Exception:
        pass
    try:
        # Strategy 2: call the package endpoint with npl_pack_id as npl_id
        # (returns list; items may include doseForm/tradeName)
        data = fass._proxy_get(f"package/{npl_pack_id}")
        items = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        for item in items:
            trade = item.get("tradeName") or item.get("name") or ""
            strength = item.get("strength") or ""
            if trade:
                return f"{trade} {strength}".strip() if strength else trade
    except Exception:
        pass
    return None


@bp.route("/manage/<token>/remove", methods=["POST"])
def remove(token):
    subscription_id = request.form.get("subscription_id", type=int)
    with get_db() as db:
        auth = _get_subscriber(db, token)
        if not auth:
            return render_template("message.html",
                title="Ogiltig länk",
                message="Länken hittades inte eller har gått ut.",
                icon="❌"), 403

        if subscription_id:
            db.execute(
                "UPDATE subscriptions SET active=0 WHERE id=? AND subscriber_id=?",
                [subscription_id, auth["subscriber_id"]],
            )
            db.commit()

    return redirect(url_for("manage.manage", token=token))
