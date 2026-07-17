"""Helpers for building search-engine-facing text (title tags, meta content)."""

TITLE_MAX_LENGTH = 60


def truncate_title(text, suffix="", max_length=TITLE_MAX_LENGTH):
    """Build a <title>/og:title/twitter:title value as `text + suffix`,
    truncating `text` (never `suffix`) on a word boundary with an ellipsis
    if the combined length would exceed max_length. Medication and category
    names come straight from the national shortage feed with no length
    limit of their own, and search engines like Bing flag or clip titles
    that run past ~60 characters."""
    text = text or ""
    full = text + suffix
    if len(full) <= max_length:
        return full

    budget = max(max_length - len(suffix), 1)
    truncated = text[:budget].rsplit(" ", 1)[0].rstrip(" ,;:-–—")
    if not truncated:
        truncated = text[:budget].rstrip()
    return truncated + "…" + suffix
