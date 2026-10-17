#!/bin/bash
# Runs only ephemeral, network-isolated containers. No push or deployment.
set -euo pipefail
docker image inspect icon2i-monitor-runtime:local --format 'RUNTIME_IMAGE {{.Id}} {{json .Config.Labels}}'
docker image inspect icon2i-monitor-test:local --format 'TEST_IMAGE {{.Id}}'
docker image inspect python:3.13-slim --format 'BASE_IMAGE {{json .RepoDigests}}'
docker image inspect prom/prometheus:v3.5.0 --format 'PROMTOOL_IMAGE {{json .RepoDigests}}'
probe_name=''
cleanup() {
  if [ -n "$probe_name" ]; then docker rm -f "$probe_name" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT
for scenario in unit healthy cold_start limits memory_caps collection_reserve total_deadline dispatcher; do
  memory=512m
  if [ "$scenario" = dispatcher ]; then memory=256m; fi
  probe_name="icon2i-probe-$scenario"
  docker create --name "$probe_name" --network none --cpus 1 \
    --memory "$memory" --memory-swap "$memory" --pids-limit 64 \
    --user 65532:65532 --cap-drop ALL --security-opt no-new-privileges \
    --read-only --tmpfs /tmp:rw,nosuid,nodev,size=67108864 \
    --env ICON2I_MONITOR_ALLOW_CLOUD=0 icon2i-monitor-test:local "$scenario"
  docker inspect "$probe_name" --format 'CONTAINER_LIMITS {{.Name}} {{json .HostConfig}}'
  set +e
  timeout --signal=TERM --kill-after=2s 120s docker start -a "$probe_name"
  probe_code=$?
  set -e
  docker inspect "$probe_name" --format 'CONTAINER_RESULT {{.Name}} {{json .State}}'
  if [ "$probe_code" -ne 0 ]; then exit "$probe_code"; fi
  test "$(docker inspect "$probe_name" --format '{{.State.ExitCode}}')" = 0
  test "$(docker inspect "$probe_name" --format '{{.State.OOMKilled}}')" = false
  docker rm "$probe_name"
  probe_name=''
done
