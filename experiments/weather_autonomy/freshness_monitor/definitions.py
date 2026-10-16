"""Pure definitions for review and future provisioning; never applies resources."""
from .core import METRICS, METRIC_PREFIX, PRODUCTS
from .schedule import PROJECT, JOB, DISPATCHER, SCHEDULER

PROM_PREFIX = "custom_googleapis_com:meteofriul_icon2i_"


def selector(metric, product):
    return (PROM_PREFIX + metric
            + '{monitored_resource="global",project_id="' + PROJECT + '",product="' + product + '"}')


def data_query(product):
    if product not in PRODUCTS:
        raise ValueError("unknown product")
    return "max by (product) (last_over_time(" + selector("critical_active", product) + "[120m])) == 1"


def absence_query():
    terms = ["absent_over_time(" + selector(metric, product) + "[90m])"
             for product in PRODUCTS for metric in METRICS]
    return "max(" + " or ".join(terms) + ") == 1"


def descriptors():
    return [{"type": METRIC_PREFIX + metric, "metricKind": "GAUGE", "valueType": "INT64", "unit": "1",
             "displayName": "ICON2I " + metric,
             "labels": [{"key": "product", "valueType": "STRING", "description": "fvg or national"}]}
            for metric in METRICS]


def policies(notification_channels=()):
    if any(not isinstance(channel, str) or not channel.startswith("projects/" + PROJECT + "/notificationChannels/")
           for channel in notification_channels):
        raise ValueError("unexpected notification channel")
    result = []
    for key, query in [(p, data_query(p)) for p in PRODUCTS] + [("telemetry", absence_query())]:
        result.append({"displayName": "ICON2I freshness - " + key, "enabled": False,
            "combiner": "OR", "severity": "CRITICAL", "notificationChannels": list(notification_channels),
            "alertStrategy": {"notificationPrompts": ["OPENED", "CLOSED"],
                "notificationChannelStrategy": [
                {"notificationChannelNames": [channel], "renotifyInterval": "21600s"}
                for channel in notification_channels]},
            "documentation": {"mimeType": "text/markdown", "content":
                "Chiusura tecnica non significa rientro verificato. Richiedere una nuova verifica completa "
                "e telemetria coerente. Cause e tentativi HTTP nei log event=icon2i_freshness_check. "
                "Completare canali email/mobile e promemoria 21600s prima dell'attivazione."},
            "conditions": [{"displayName": key, "conditionPrometheusQueryLanguage": {
                "query": query, "duration": "0s", "evaluationInterval": "60s"}}]})
    return result


def queries():
    base = 'resource.type="cloud_run_job"\nresource.labels.project_id="meteo-friul"\nresource.labels.job_name="meteofriul-icon2i-freshness"\njsonPayload.event="icon2i_freshness_check"\n'
    return [
        {"displayName": "ICON2I - Attenzione eta e copertura", "query":
         base + '(jsonPayload.causes="run_age_attention" OR jsonPayload.causes="coverage_attention")'},
        {"displayName": "ICON2I - Indeterminati ultimi sei slot", "query":
         base + "(jsonPayload.check_state=3 OR jsonPayload.indeterminate_count_last6>0)"},
        {"displayName": "ICON2I - Confronti HTTP", "query":
         base + "(jsonPayload.http_comparison.ordinary.result:* OR jsonPayload.http_comparison.resolve.ordinary.result:*)"},
    ]


def deployment_plan():
    return {
        "status": "LOCAL_REVIEW_ONLY_NOT_APPLIED", "project": PROJECT, "region": "europe-west1",
        "job": {"name": JOB, "command": ["python", "-m", "freshness_monitor"],
                "argsViaOverridesOnly": True, "imageDefaultArgs": ["--help"], "cpu": "1", "memory": "512Mi",
                "taskCount": 1, "parallelism": 1, "timeout": "120s", "maxRetries": 0,
                "cloudOptInDefault": False, "totalApplicationBudgetSeconds": 110,
                "collectionBudgetSeconds": 75, "perProductCollectionBudgetSeconds": 35},
        "dispatcher": {"name": DISPATCHER, "private": True, "minInstances": 0,
                       "maxInstances": 1, "cpu": "1", "memory": "256Mi",
                       "billing": "request-based", "concurrency": 8, "timeout": "20s",
                       "command": ["python", "-m", "freshness_monitor.dispatcher"],
                       "args": ["--serve", "--cloud"], "cloudOptInDefault": False,
                       "path": "/dispatch", "launchAttemptsPerDelivery": 1,
                       "sourceTimestampOffsetLimitSeconds": 120,
                       "deduplication": "monitor CAS/outbox per product and original slot"},
        "scheduler": {"name": SCHEDULER, "target": "private dispatcher /dispatch (URL after deployment)",
                      "authentication": "OIDC; audience is dispatcher service base URL",
                      "body": {}, "schedule": "10,40 * * * *", "timeZone": "UTC",
                      "retryCount": 0, "maxRetryDuration": "0s", "attemptDeadline": "30s",
                      "activationRequiresSeparateAuthorization": True},
        "transitionGraceSeconds": {"fvg": 60, "national": 60},
        "graceRationale": "30s verified reader cache + 30s initial request/propagation allowance; validate at activation.",
        "state": {"bucket": "meteo-friul-weather-state", "prefix": "monitoring/icon2i-freshness/v1/"},
        "data": {"bucket": "meteo-friul-weather-data", "readOnly": True},
        "permissions": {"weather": ["storage.objects.get", "storage.objects.list"],
                        "stateTwoObjectsOnly": ["storage.objects.get", "storage.objects.create", "storage.objects.delete"],
                        "monitoring": ["monitoring.timeSeries.create", "monitoring.timeSeries.list"],
                        "dispatcherOnMonitorJobOnly": ["run.jobs.run", "run.jobs.runWithOverrides"],
                        "schedulerOnDispatcherOnly": ["run.routes.invoke"]},
        "pending": ["authorize image/build and activation", "verify private IAM and observed Scheduler header through deployed dispatcher",
                    "measure grace, dispatcher cost and runtime", "configure email/mobile channels and 6h renotification",
                    "verify log retention for 14 days plus review margin",
                    "verify live policies, IAM scope and notification delivery"],
    }
