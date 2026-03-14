# Hanauta Service

`hanauta-service` is the first C-based background service for Hanauta.

Current scope:

- writes a heartbeat/status file to `~/.local/state/hanauta/service/status.json`
- periodically refreshes cached weather data to `~/.local/state/hanauta/service/weather.json`
- periodically refreshes cached crypto data to `~/.local/state/hanauta/service/crypto.json`

This first iteration shells out to `jq` and `curl` so we can move slow network work off the UI path right away while the service architecture settles.

Build:

```bash
./hanauta/src/service/build.sh
```

If the binary exists at `hanauta/bin/hanauta-service`, `startup.sh` will launch it automatically.
