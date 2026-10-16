"""Shared conservative checks on event-scoped text, never whole listings."""
from html import unescape
import re


NOTICE_PATTERN = re.compile(
    r"\b(?:annullat[oaie]|rinviat[oaie]|posticipat[oaie]|sospes[oaie]|"
    r"cancellat[oaie]|riprogrammat[oaie]|cambio\s+(?:di\s+)?(?:sede|orario)|"
    r"nuova\s+data)\b", re.I)
WEATHER_CONDITION = re.compile(
    r"\b(?:in\s+caso\s*di|qualora)\b[^.!?;\n]{0,75}"
    r"\b(?:maltempo|cattivo\s+tempo|pioggia|condizioni\s+meteo)\b", re.I)
EVENT_SUBJECT = re.compile(
    r"\b(?:evento|spettacolo|concerto|manifestazione|replich?e?|visite?|"
    r"apertura|attivita|mercatino|festa|gara|escursione|incontro|programma)\b", re.I)


def schedule_notice(*fragments):
    text = "\n".join(unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
                    for value in fragments)
    for match in NOTICE_PATTERN.finditer(text):
        left = text[max(0, match.start() - 110):match.start()]
        right = text[match.end():min(len(text), match.end() + 85)]
        # A weather contingency is not evidence that the event has changed.
        clause_left = re.split(r'[.!?;\n]|\b(?:ma|però|tuttavia|invece)\b', left, flags=re.I)[-1]
        clause_right = re.split(r'[.!?;\n]', right)[0]
        # Do not let one conditional notice suppress another nearby notice.
        previous_notices = list(NOTICE_PATTERN.finditer(clause_left))
        if previous_notices:
            between = clause_left[previous_notices[-1].end():]
            if not re.fullmatch(r'\s*(?:o|oppure|e)\s*', between, re.I):
                clause_left = between
        previous_end = 0
        for following_notice in NOTICE_PATTERN.finditer(clause_right):
            between = clause_right[previous_end:following_notice.start()]
            if not re.fullmatch(r'\s*(?:o|oppure|e)\s*', between, re.I):
                clause_right = clause_right[:following_notice.start()]
                break
            previous_end = following_notice.end()
        clause = clause_left + match[0] + clause_right
        # Present tense can state a policy ("viene annullato in caso di ...").
        # Explicit factual statements remain notices even beside a condition.
        actual = re.search(r"\b(?:e|è|sono|era|erano)\s+(?:stat[oaie]\s+)?$",
                           clause_left, re.I)
        if WEATHER_CONDITION.search(clause) and not actual:
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
