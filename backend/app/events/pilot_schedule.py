"""Shared conservative checks on event-scoped text, never whole listings."""
from html import unescape
import re


NOTICE_PATTERN = re.compile(
    r"\b(?:annullat[oaie]|rinviat[oaie]|posticipat[oaie]|sospes[oaie]|"
    r"cancellat[oaie]|riprogrammat[oaie]|cambio\s+(?:di\s+)?(?:sede|orario)|"
    r"nuova\s+data)\b", re.I)
WEATHER_CONDITION = re.compile(
    r"\b(?:in\s+caso\s+di|qualora)\b.{0,75}"
    r"\b(?:maltempo|cattivo\s+tempo|pioggia|condizioni\s+meteo)\b", re.I)
EVENT_SUBJECT = re.compile(
    r"\b(?:evento|spettacolo|concerto|manifestazione|replich?e?|visite?|"
    r"apertura|attivita|mercatino|festa|gara|escursione|incontro|programma)\b", re.I)


def schedule_notice(*fragments):
    text = " ".join(unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
                    for value in fragments)
    for match in NOTICE_PATTERN.finditer(text):
        left = text[max(0, match.start() - 110):match.start()]
        right = text[match.end():min(len(text), match.end() + 85)]
        # A weather contingency is not evidence that the event has changed.
        if WEATHER_CONDITION.search(left + match[0] + right):
            continue
        term = match[0].lower()
        if term.startswith('sospes'):
            if re.match(r'\s+(?:tra|fra|durante)\b', right, re.I):
                continue
            if (re.search(r'\b(?:conto|tempo|spazio|atmosfera|universo)\s+(?:in\s+)?$', left, re.I)
                    or not EVENT_SUBJECT.search(left[-55:] + right[:25])
                    and text.strip().lower() != term):
                continue
        if term.startswith('cancellat') and not EVENT_SUBJECT.search(left[-55:] + right[:25]):
            if text.strip().lower() != term:
                continue
        return True
    return False


def require_schedule_review(*fragments):
    if schedule_notice(*fragments):
        raise ValueError("schedule_change_requires_review")
