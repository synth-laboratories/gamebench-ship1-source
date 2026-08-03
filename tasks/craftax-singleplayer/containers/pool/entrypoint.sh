#!/bin/sh
# Start the Rust engine, wait for it, then hand the container to the Python
# policy service.
#
# Two processes, one container, and a deliberate ordering: the pool probes
# /health on the Python service and treats a 200 as "ready to take rollouts".
# If Python came up first, that 200 would be a lie — the engine behind it might
# still be binding, and the first POST /rollout would fail with a connection
# error the pool would report as a rollout failure rather than a cold start.
#
# The engine is also the reason `exec` is used for the policy service: the
# policy must be PID 1's foreground process so a container stop signal reaches
# it, and so its exit is the container's exit.

set -eu

GOLD_PORT="${CRAFTAX_GOLD_PORT:-8098}"
GOLD_HOST="${CRAFTAX_GOLD_HOST:-127.0.0.1}"
POLICY_PORT="${PORT:-8104}"
READY_TIMEOUT_S="${CRAFTAX_GOLD_READY_TIMEOUT_S:-60}"

/usr/local/bin/craftax_gold --host "${GOLD_HOST}" --port "${GOLD_PORT}" &
GOLD_PID=$!

# If the engine dies later, take the container down rather than serve a policy
# service that 502s every rollout. A pool can reschedule a dead container; it
# cannot do anything with a half-dead one.
trap 'kill -TERM "${GOLD_PID}" 2>/dev/null || true' TERM INT

waited=0
until python -c "
import sys, urllib.request
try:
    urllib.request.urlopen('http://${GOLD_HOST}:${GOLD_PORT}/health', timeout=1).read()
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    if ! kill -0 "${GOLD_PID}" 2>/dev/null; then
        echo "craftax_gold exited before becoming healthy" >&2
        exit 1
    fi
    waited=$((waited + 1))
    if [ "${waited}" -ge "${READY_TIMEOUT_S}" ]; then
        echo "craftax_gold did not become healthy in ${READY_TIMEOUT_S}s" >&2
        kill -TERM "${GOLD_PID}" 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

echo "craftax_gold healthy on ${GOLD_HOST}:${GOLD_PORT}; starting policy service on :${POLICY_PORT}" >&2

# The Python client defaults CRAFTAX_GOLD_URL to :8103, which is not the port
# the engine binds. Set it explicitly rather than relying on that default —
# getting this wrong produces a service that passes /health and then fails
# every rollout, which is the most expensive way to be wrong here.
export CRAFTAX_GOLD_URL="${CRAFTAX_GOLD_URL:-http://${GOLD_HOST}:${GOLD_PORT}}"
export PORT="${POLICY_PORT}"

exec python -m containers.react.craftax_singleplayer_container
