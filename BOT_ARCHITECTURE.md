# ChampionsKOF BOT Architecture

## Boundary rule

BOT code must never change or call internal netplay core code directly. The forbidden area includes rollback, UDP/P2P/relay internals, jitter buffer, synchronization, save state, input delay and frame transport logic.

The BOT is an external automated client:

```text
bot supervisor process
        |
        v
public matchmaking HTTP API
        |
        v
existing ChampionsKOF --match-window process
        |
        v
public RollbackNetplaySession surface
        |
        v
netplay core, unchanged
```

The only gameplay path allowed for a BOT is the same path used by a normal player process.

## Phases

- BOT v0: login/register a bot user, create or join a public room, occupy seat 1, launch the normal match window and send neutral input.
- BOT v1: same as v0, but enables the existing scripted input surface through `CHAMPIONS_NETPLAY_SCRIPTED_INPUTS=1`.
- BOT v2: add game-specific heuristics outside the player frame loop. Any observation channel must be public, coarse and non-invasive.
- BOT v3: smarter decision services are allowed only out of process. Heavy inference must never run in the player's frame loop.

## Current implementation

`bots/champions_bot_runner.py` is a small external supervisor. It:

- authenticates with `/api/auth/login` or `/api/auth/register`;
- uses `/api/rooms`, `/api/rooms/{id}` and `/api/rooms/{id}/join`;
- creates a named bot room when one does not exist;
- launches the existing executable with `--match-window`, `--netplay-room`, `--netplay-token`, `--netplay-seat` and relay arguments;
- keeps BOT v0 neutral by setting `CHAMPIONS_NETPLAY_SCRIPTED_INPUTS=0`;
- enables BOT v1 only by setting `CHAMPIONS_NETPLAY_SCRIPTED_INPUTS=1`.

It does not import Qt, does not link against emulator code and does not modify `rollback_netplay_session.*`.

## Example

```powershell
python .\bots\champions_bot_runner.py `
  --base-url http://127.0.0.1:8080/ `
  --exe .\out\build\x64-release\FBNeoLibTester.exe `
  --driver kof2002 `
  --rom-dir C:\roms `
  --game-zip C:\roms\kof2002.zip `
  --bios-zip C:\roms\neogeo.zip `
  --slot 1 `
  --mode v0 `
  --config-dir .\local_lab\bots\kof2002-01\config `
  --log-dir .\local_lab\bots\kof2002-01\logs
```

Use `--mode v1` only after v0 has passed gates.

## Gates

Every BOT change must keep these gates green:

- `powershell -ExecutionPolicy Bypass -File .\tools\check_netplay_architecture_guard.ps1`
- `powershell -ExecutionPolicy Bypass -File .\tools\verify_video_policy.ps1`
- netplay regression suite with desync = 0
- audio underrun = 0
- frame p95/p99 without regression
- update p95 without regression
- no BOT-caused stall in traces

The BOT runner itself has unit tests:

```powershell
python -m unittest bots.test_champions_bot_runner
```

## Lura VPS deployment

The first Linux VPS deployment assets live in `deploy/lura/`.

They prepare a single-node server for:

- matchmaking API;
- realtime relay;
- one external KOF2002 BOT;
- initial avatar storage budget.

The deployment keeps the BOT out of the netplay core. The BOT service launches
`bots/champions_native_bot.py` for the native lightweight v0 path. This v0 bot
uses the public HTTP API to authenticate, occupy a room seat, keep room
presence alive and write metrics. It can also open its own UDP socket and speak
the public relay packet contract as an external client: `hello`, `ping`, `pong`,
`bootstrap-ready`, `bootstrap-go` and neutral `frame` packets.

The native Linux BOT does not import or call rollback, save-state, emulator,
jitter-buffer, transport or sync internals. For relay bootstrap it uses the same
consensus hash expected by the public relay path,
`sha256(room_id:epoch:relay-bootstrap-ready)`, then waits for `bootstrap-go`
before sending neutral inputs.

`bots/champions_bot_runner.py` remains available for the full-client path, where
the bot supervisor launches the normal match client with public command-line
arguments.
