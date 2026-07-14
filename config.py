"""Shared environment-derived configuration used across multiple modules."""

import os

SITE_URL = os.getenv("SITE_URL", "").rstrip("/")

# How long a subscription stays active before it needs renewing, and the TTL
# for the unsubscribe/manage tokens tied to it. One constant instead of the
# same "30 * 24" / "days=30" literal repeated independently across files.
SUBSCRIPTION_TTL_DAYS = 30

# Minimum time between two notification emails for the same subscription --
# a pharmacy's live stock status can flicker in/out several times within a
# single day (per Fass's own docs), so a plain "notify once per restock"
# rule sends far too many emails. Replaces the old approach of clearing
# last_notified_at as soon as a product was confirmed out of stock again.
NOTIFY_COOLDOWN_HOURS = 24


def token_url(site_url, kind, token):
    """Build a token-bearing URL (manage/confirm/unsubscribe/extend) --
    the one place this "{site_url}/{kind}/{token}" shape is formatted,
    instead of independently in routes/subscribe.py, routes/extend.py and
    every mail.py send_* function."""
    return f"{site_url}/{kind}/{token}"
