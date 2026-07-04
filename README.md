# urirun-service-chat

Standalone urirun chat/operator dashboard service.

This package gives the chat dashboard its own installable service shape, like
`urirun-connector-*` packages do for URI capabilities. The implementation is
currently a thin wrapper around `urirun.host.host_dashboard`, so the existing
chat UI, URI invocation, artifacts, widgets, node discovery and scanner controls
stay in one place while the service boundary becomes explicit.

The operator-level flow is documented in
`/home/tom/github/if-uri/urirun/docs/HOST_DASHBOARD_CHAT.md`: natural language
input, target selection, deterministic URI intents, service control, artifacts,
widgets and `urifix://` recovery.

## Defaults

- service id: `chat`
- default port: `8194`
- default bind: `127.0.0.1`
- env port override: `URIRUN_CHAT_PORT`
- env host override: `URIRUN_CHAT_HOST`

## Run

```bash
urirun-service-chat serve --project /home/tom/github/if-uri/urirun --db ~/.urirun/host.db
```

Then open:

```text
http://127.0.0.1:8194/
```

`serve` replaces an older `urirun-service-chat` process that is still listening
on the same port, so a stale `8194` holder does not fail with
`Address already in use`. Use `--no-replace` to disable that behavior, or
`--force-replace` only in a controlled development environment when the port is
known to be disposable.

You can also spell the intent explicitly:

```bash
urirun-service-chat restart --project /home/tom/github/if-uri/urirun --db ~/.urirun/host.db --port 8194
```

With a node:

```bash
urirun-service-chat serve \
  --project /home/tom/github/if-uri/urirun \
  --db ~/.urirun/host.db \
  --node-url lenovo=http://192.168.188.201:8766
```

## URI surface

The chat service exposes the same dashboard endpoints as the current host
dashboard, including:

- `/api/chat/ask`
- `/api/chat/history`
- `/api/chat/messages/delete`
- `/api/artifacts`
- `/api/artifacts/delete`
- `/api/artifacts/dedupe`
- `/api/artifacts/cleanup-orphans`
- `/api/services/live`
- `/api/uri/invoke`

Natural-language commands enter through `/api/chat/ask`. Common operations such
as starting the phone scanner and syncing archived documents to a node are
planned deterministically before any LLM planner is used. General prompts use
mesh discovery and require `URIRUN_LLM_MODEL` or `LLM_MODEL` unless they can be
handled by a no-LLM heuristic.

When the browser has stale node query parameters but the user did not explicitly
select a node and the prompt does not name one, `/api/chat/ask` resolves the run
to `selectedTargets: ["host"]`. The mesh is filtered before planning, so a
prompt such as `opublikuj post na LinkedIn` does not accidentally plan against a
previously selected remote node.

The system-message roll-up treats a URI step as successful only when both the
timeline step and the nested execution envelope are successful. In particular,
`results[step.id].result.value.ok == false` prevents a green `ok: N URI step(s)`
summary even if the transport wrapper itself returned `ok: true`.

## Restart through URI

The chat service can expose a restart action through the dashboard URI invoke
API:

```text
dashboard://host/service/chat/command/restart
service://host/chat/command/restart
service://chat/command/restart
```

Without a configured supervisor, the dashboard schedules
`urirun-service-chat restart ...`, which replaces the old chat process on the
same port. For an external supervisor you can still use `systemd --user`:

For `systemd --user`:

```bash
curl -X POST http://127.0.0.1:8194/api/uri/invoke \
  -H 'Content-Type: application/json' \
  -d '{"uri":"service://host/chat/command/restart","mode":"execute","payload":{"manager":"systemd","unit":"urirun-service-chat.service"}}'
```

Or configure the restart command outside the prompt:

```bash
export URIRUN_CHAT_RESTART_CMD='systemctl --user restart urirun-service-chat.service'
```

The service manifest is available from Python:

```python
from urirun_service_chat import urirun_service

print(urirun_service())
```
