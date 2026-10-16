"""Small, attributed excerpts for verified pilot event detail pages."""
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit


MAX_EXCERPT_LENGTH = 180
EXCERPT_FIELDS = (
    "description_excerpt",
    "description_source_name",
    "description_source_url",
    "description_checked_at",
)


def clean_excerpt_text(value):
    text = re.sub(r"<[^>]+>", " ", unescape(str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=\w)\s+(?=[’'])", "", text)


def make_excerpt(value, *, title="", max_length=MAX_EXCERPT_LENGTH):
    """Return a bounded excerpt without manufacturing or joining source copy."""
    text = clean_excerpt_text(value)
    normalized_title = clean_excerpt_text(title).casefold()
    if len(text) < 20 or text.casefold() == normalized_title:
        return ""
    if len(text) <= max_length:
        return text

    candidate = text[:max_length]
    sentence_boundaries = [match.end() for match in re.finditer(r"[.!?](?=\s|$)", candidate)]
    useful_sentence = next((boundary for boundary in reversed(sentence_boundaries)
                            if boundary >= int(max_length * 0.55)), None)
    if useful_sentence:
        return candidate[:useful_sentence].strip()
    last_space = candidate[:max_length - 1].rfind(" ")
    boundary = last_space if last_space >= int(max_length * 0.72) else max_length - 1
    return candidate[:boundary].rstrip(" ,;:-") + "…"


class _MetaDescriptionParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.descriptions = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() != "meta":
            return
        values = {str(key).casefold(): value for key, value in attrs}
        kind = str(values.get("name") or values.get("property") or "").casefold()
        content = values.get("content")
        if kind in {"description", "og:description"} and content:
            self.descriptions.append(content)


def extract_meta_excerpt(html, *, title=""):
    parser = _MetaDescriptionParser()
    parser.feed(str(html or ""))
    for description in parser.descriptions:
        excerpt = make_excerpt(description, title=title)
        if excerpt:
            return excerpt
    return ""


def attributed_excerpt(value, *, source_name, source_url, title="", checked_at=None):
    """Build catalogue fields only when source identity and HTTPS URL are explicit."""
    excerpt = make_excerpt(value, title=title)
    parsed = urlsplit(str(source_url or ""))
    source_name = clean_excerpt_text(source_name)
    if not excerpt or not source_name or parsed.scheme != "https" or not parsed.hostname:
        return {}
    return {
        "description_excerpt": excerpt,
        "description_source_name": source_name,
        "description_source_url": source_url,
        "description_checked_at": checked_at or datetime.now(timezone.utc).isoformat(),
    }


def remove_cross_page_duplicates(events):
    """Drop likely site boilerplate repeated on different event detail URLs."""
    urls_by_excerpt = {}
    for event in events:
        excerpt = event.get("description_excerpt")
        url = event.get("description_source_url")
        if excerpt and url:
            urls_by_excerpt.setdefault(excerpt.casefold(), set()).add(url)
    repeated = {excerpt for excerpt, urls in urls_by_excerpt.items() if len(urls) > 1}
    if not repeated:
        return events
    for event in events:
        if str(event.get("description_excerpt") or "").casefold() in repeated:
            for key in EXCERPT_FIELDS:
                event.pop(key, None)
    return events
