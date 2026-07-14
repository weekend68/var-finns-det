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

# Minimum number of consecutive polls with a new status before a stock-status
# flip is trusted as real, rather than a single noisy measurement -- fass.py's
# own check_stock() regularly logs incomplete per-poll coverage (e.g. "50/1453
# apotek kunde inte kollas"), so any one poll's pharmacy_count can swing to/
# from 0 even though the medication's actual stock status hasn't changed.
# Shared between two different mechanisms that both apply this same principle:
#   - checker.py's polling_loop(): a streaming state machine filtering one
#     live poll at a time (_consecutive_zeros/_consecutive_positives).
#   - routes/lakemedel.py's _stock_history(): a batch analysis replaying
#     already-stored poll_log rows to find the same kind of confirmed flip.
MIN_CONSECUTIVE_POLLS = 2


def token_url(site_url, kind, token):
    """Build a token-bearing URL (manage/confirm/unsubscribe/extend) --
    the one place this "{site_url}/{kind}/{token}" shape is formatted,
    instead of independently in routes/subscribe.py, routes/extend.py and
    every mail.py send_* function."""
    return f"{site_url}/{kind}/{token}"
