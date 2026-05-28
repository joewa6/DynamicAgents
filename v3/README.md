# DynamicAgents V3

V3 is the fun/stable interactive build.

The goal of this version is visible group dynamics at human-observable speed:

- small populations, usually 10-200 agents
- target population control around 80 agents
- founding gene distribution setup before each run
- persistent social bonds and birth rings
- slow-motion playback modes for watching groups form

Run it with:

```bash
julia --threads=auto --project=. run.jl
```

Then open:

```text
http://localhost:8000
```

## Version Note

The current V3 server loop is intentionally paced for visualization. It supports
slow modes such as one simulation tick every 10, 100, or 1000 rendered frames.

The previous rapid loop, before the slow-motion speed control was added, should
be treated as the seed for V4: a faster performance/search-oriented version for
headless runs, parameter sweeps, and scoring candidate regimes.

## Render Deploy

V3 is deployable as a Render web service.

Use the repository blueprint in the root `render.yaml`, or create a Render web
service manually with:

- runtime: Docker
- Dockerfile path: `v3/Dockerfile`
- Docker context: `v3`

Render provides the `PORT` environment variable. The V3 server serves both the
static app and WebSocket stream from that single port. The WebSocket endpoint is
`/ws`.
