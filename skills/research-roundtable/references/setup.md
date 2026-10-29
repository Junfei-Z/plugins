# Setup and host integration

## Install through magpie

Install Research Roundtable from **Library → Market → Skills**, then enable
it for each participating agent. magpie distributes the skill; each host
still needs to be running and able to invoke Python. Reload skills or start
a fresh session if a host does not discover it automatically.

Once this contribution is merged, the repository can also be installed with:

```sh
npx skills add magpie-community/plugins --skill research-roundtable
```

For local development, import `skills/research-roundtable` from this checkout
through magpie's Library page. Resolve the helper from the loaded skill's
actual directory; do not assume every agent uses Codex's skill root.

The skill does not install another agent, change model routing or read
provider credentials. If the user asks to change models, use magpie's normal
agent model settings independently of the channel setup. Two different
models in one host are not automatically two independent agent processes.

## Shared channel

All participants must run on the same machine and use the same channel
directory. The compatibility default is `/tmp/claude-channels`. For a
separate, persistent location, set `RESEARCH_ROUNDTABLE_DIR` to the same
user-owned directory in both hosts before running the helper. On Windows,
use a writable directory for this variable and the host's Python command.

The transcript is append-only NDJSON:

```json
{"from":"reviewer","ts":1710000000,"text":"Challenge the novelty claim."}
```

Each identity has an independent integer cursor. Names accept 1–80 ASCII
letters, digits, dots, underscores or hyphens, beginning with a letter or
digit. Agent names must be distinct within a channel. The `from` field is
a label, not an authenticated identity: another local process with write
access can impersonate it.

## Handshake

Resolve the installed helper's path in each host. Run `setup` once for each
identity before sending; it starts that identity's cursor at the current
end. Do not rerun it to reconnect a live participant, as that skips unread
messages. Use `history` and `status` to inspect an existing channel instead.

In the proposer host:

```sh
python3 /absolute/path/to/scripts/channel.py setup idea-v1 proposer
```

In the reviewer host:

```sh
python3 /absolute/path/to/scripts/channel.py setup idea-v1 reviewer
```

Choose a unique nonce. Send `[HANDSHAKE] Reply exactly CHANNEL_OK <nonce>`
as the proposer, using `send idea-v1 proposer --stdin`. Have the reviewer
receive it and reply as `reviewer`, then have the proposer confirm receipt.
Inspect history and both cursors. This proves the round trip, not continuous
background operation.

## Receive modes

| Host capability | Helper command | Limit |
|---|---|---|
| Active, turn-based agent | `listen CHANNEL AGENT --timeout 30` | Returns after a message or timeout; re-arm while the discussion is active |
| Tool completion can resume the host | `wait CHANNEL AGENT` | Blocks for one batch; re-arm after handling it |
| Streaming tool output can resume the host | `stream CHANNEL AGENT` | Remains running; stop it when the discussion ends |

The other commands are `send`, `poll`, `history`, `status` and `leave`.
`poll` returns immediately, `history` does not consume messages, and `leave`
appends a departure notice without deleting the transcript. Receive commands
advance that identity's cursor; do not run competing listeners under one
identity. `status.pending_lines` counts unread transcript lines, including
the identity's own messages; it is not a count of actionable peer messages.

## Optional bridge and provenance

This community skill intentionally omits the optional Codex SDK bridge,
the upstream installer and service setup. A persistent bridge consumes
model allowance and needs separate authorization and lifecycle management.
See the upstream [bridge README](https://github.com/Junfei-Z/research-roundtable/tree/main/bridge)
if the user explicitly requests it; do not download or start it automatically.

The channel helper and research protocol are copied unchanged from
[research-roundtable, commit 6823bab](https://github.com/Junfei-Z/research-roundtable/tree/6823bab0d344cbc398f2a33c378b3320bdaf3bf8).
The entrypoint and this setup guide adapt their packaging to magpie.
The original MIT notice is retained in `../LICENSE`.
