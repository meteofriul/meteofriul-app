"""Monthly reminder delivery. SMTP acceptance is not proof of inbox delivery."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime
import hashlib
import json
import os
from pathlib import Path
import re
import smtplib
import ssl
import uuid

from .model import MarketError, encode, timestamp
from .review import ROME, reminder, review_queue


def email_address(value):
    if not isinstance(value, str) or len(value) > 254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", value):
        raise MarketError("markets_email_address_invalid")
    local, domain = value.rsplit("@", 1)
    if local.startswith(".") or local.endswith(".") or ".." in value or len(local) > 64:
        raise MarketError("markets_email_address_invalid")
    return local + "@" + domain.lower()


def smtp_config():
    keys = {key: os.getenv("MARKETS_REMINDER_SMTP_" + key.upper(), "") for key in ("host", "username", "password", "from")}
    if not all(keys.values()):
        return None
    keys["from"] = email_address(keys["from"])
    if not re.fullmatch(r"[a-zA-Z0-9.-]+", keys["host"]):
        raise MarketError("markets_email_smtp_invalid")
    return keys


def public_settings(record, repository):
    settings = record.get("emailReminder", {})
    configured = all(os.getenv("MARKETS_REMINDER_SMTP_" + key) for key in ("HOST", "USERNAME", "PASSWORD", "FROM"))
    if not configured and repository.storage == "sqlite":
        folder = repository.path.parent / "email"
        configured = all((folder / name).is_file() for name in ("smtp.json", "credential.xml", "task.json"))
    delivery = copy.deepcopy(settings.get("delivery"))
    if delivery and delivery["status"] == "sending":
        delivery["status"] = "uncertain"  # Crash or concurrent send: never assert delivery.
    return {"recipient": settings.get("recipient", ""), "enabled": settings.get("enabled", False),
            "senderConfigured": configured, "lastDelivery": delivery}


def message_for(record, *, config, now):
    schedule = reminder(record, now=now)
    message = EmailMessage()
    message["From"] = config["from"]
    message["To"] = email_address(record["emailReminder"]["recipient"])
    message["Subject"] = f"Meteo Friûl · revisione mercati {schedule['period']}"
    message["Date"] = format_datetime(now)
    message["Message-ID"] = f"<markets-review-{uuid.uuid4()}@{config['from'].rsplit('@', 1)[1]}>"
    extra = "Rivedi anche i calendari stagionali e cerca nuove fonti ufficiali.\n" if schedule["kind"] == "quarterly" else ""
    message.set_content(
        "È il momento della revisione periodica di Mercati e mercatini.\n\n"
        f"Fonti da approfondire: {len(review_queue(record))} schede.\n"
        "Apri il pannello Meteo Friûl: Scopri → Mercati e mercatini → Verifiche.\n"
        "Consulta le fonti, aggiorna le schede e conserva note e considerazioni utili.\n" + extra +
        "Quando hai concluso, registra l’esito della revisione nel pannello.\n\n"
        "Gli aggiornamenti automatici continuano senza attendere questa revisione.\n"
        "Puoi cambiare il destinatario o disattivare queste email dal pannello.\n")
    return message


def send_smtp(message, config):
    connection = None
    stage = "connect"
    try:
        # Implicit TLS only; no plaintext fallback, debug log or provider bodies.
        connection = smtplib.SMTP_SSL(config["host"], 465, timeout=30, context=ssl.create_default_context())
        connection.login(config["username"], config["password"])
        stage = "send"
        connection.send_message(message)
        return {"status": "accepted", "errorCode": None}
    except smtplib.SMTPAuthenticationError:
        return {"status": "failed", "errorCode": "authentication_failed"}
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError):
        return {"status": "failed", "errorCode": "message_rejected"}
    except Exception:
        return {"status": "uncertain" if stage == "send" else "failed",
                "errorCode": "delivery_unknown" if stage == "send" else "connection_failed"}
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def _update(repository, operation, change):
    for _ in range(6):
        current = repository.read()
        try:
            return repository.mutate(expected_revision=current["revision"], operation_id=operation,
                                     request_hash=hashlib.sha256(operation.encode()).hexdigest(), change=change)[0]
        except MarketError as error:
            if error.detail["code"] != "markets_revision_conflict":
                raise
    raise MarketError("markets_email_busy", 409)


def _delivery_revision(current, delivery):
    result = copy.deepcopy(current)
    result["emailReminder"]["delivery"] = delivery
    result["revision"] += 1
    result["audit"].append({"revision": result["revision"], "action": "email-reminder", "at": timestamp(),
                            "actor": "markets-reminder", "reason": "Promemoria email: " + delivery["status"], "changes": []})
    return result


def run(repository, *, now=None, config=None, sender=send_smtp):
    now = (now or datetime.now(ROME)).astimezone(ROME)
    current = repository.read()
    settings = current.get("emailReminder", {})
    schedule = reminder(current, now=now)
    if not settings.get("enabled"):
        return {"status": "disabled"}
    if not schedule["due"]:
        return {"status": "not_due"}
    config = config or smtp_config()
    if not config:
        return {"status": "not_configured"}
    period = schedule["period"]
    operation = "reminder-" + str(uuid.uuid4())

    def claim(record):
        settings = record.get("emailReminder", {})
        latest = reminder(record, now=now)
        if not settings.get("enabled") or not latest["due"] or latest["period"] != period:
            raise MarketError("markets_email_no_longer_due", 409)
        previous = settings.get("delivery", {})
        if previous.get("period") == period and (previous.get("status") not in {"failed", "cancelled"} or
                previous.get("status") == "failed" and previous.get("attemptedAt", "")[:10] == now.date().isoformat()):
            raise MarketError("markets_email_already_attempted", 409)
        delivery = {"id": operation, "period": period, "recipient": email_address(settings.get("recipient")),
                    "attemptedAt": now.isoformat(), "status": "sending", "errorCode": None}
        return _delivery_revision(record, delivery)

    try:
        claimed = _update(repository, operation, claim)
    except MarketError as error:
        if error.detail["code"] in {"markets_email_already_attempted", "markets_email_no_longer_due"}:
            return {"status": "skipped"}
        raise
    # Save a durable reservation before talking to SMTP. An interrupted send
    # stays uncertain and is not resent automatically in the same period.
    latest = repository.read()
    if (latest["emailReminder"].get("recipient") != claimed["emailReminder"].get("recipient") or
            not latest["emailReminder"].get("enabled") or not reminder(latest, now=now)["due"]):
        outcome = {"status": "cancelled", "errorCode": None}
    else:
        try:
            outcome = sender(message_for(claimed, config=config, now=now), config)
        except Exception:
            outcome = {"status": "uncertain", "errorCode": "delivery_unknown"}

    def finish(record):
        delivery = record["emailReminder"]["delivery"]
        if delivery["id"] != operation:
            raise MarketError("markets_email_delivery_conflict", 409)
        return _delivery_revision(record, {**delivery, **outcome, "finishedAt": timestamp()})

    _update(repository, operation + "-result", finish)
    return {"status": outcome["status"], "period": period, "errorCode": outcome["errorCode"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-connection", action="store_true")
    args = parser.parse_args()
    try:
        config = smtp_config()
        if args.check_connection:
            if not config:
                raise MarketError("markets_email_not_configured")
            connection = smtplib.SMTP_SSL(config["host"], 465, timeout=30, context=ssl.create_default_context())
            try:
                connection.login(config["username"], config["password"])
            finally:
                connection.close()
            result = {"status": "connection_ok", "emailSent": False}
        else:
            if os.getenv("MARKETS_STORAGE") != "sqlite" or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB"):
                raise MarketError("markets_email_local_only")
            path = Path(os.getenv("MARKETS_SQLITE_PATH", ""))
            if not path.is_file():
                raise MarketError("markets_email_archive_missing")
            from .repository import SQLiteMarketRepository
            result = run(SQLiteMarketRepository(path), config=config)
        print(json.dumps(result))
        return 1 if result["status"] in {"failed", "uncertain", "not_configured"} else 0
    except Exception:
        print(json.dumps({"status": "failed", "errorCode": "email_configuration_or_delivery_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
