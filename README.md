# GPU Warm-Up Tool

A Python tool that warms up GPU instances behind a Genesys Cloud Web Messaging deployment by sending a configurable message as new conversations, repeated a configurable number of times.

## Why?

When changes are made to GPU-backed deployments, the first real user conversations can be slow while instances cold-start. This tool pre-warms them so end users get fast responses from the start.

## Session Behaviour

Each warm-up iteration opens a new Web Messaging conversation and runs this sequence:

1. Connect, join the session, and wait for the bot welcome message.
2. Send the configured **warm-up message** (default: `Warming up!`).
3. On each subsequent agent reply, send the **escalation message** (default: `I want to talk to human agent`).
4. Repeat step 3 until the agent replies with the **disconnect message** (default: `Disconnecting now`; leading/trailing whitespace is ignored).
5. Close the WebSocket and proceed to the next iteration.

The deployment bot flow must be configured to eventually respond with the disconnect message when the user requests a human agent; otherwise the iteration will time out. **Time to First Response** is measured from sending the warm-up message to the first agent reply.

Iterations run sequentially — the next iteration does not start until the current conversation receives the disconnect message and disconnects.

## Quick Start

### Web UI

```bash
pip install -r requirements.txt
python app.py
```

Open [http://localhost:5001](http://localhost:5001), fill in your deployment details, and hit **Start Warm-Up**.

### CLI

```bash
python -m src.cli \
  --deployment-id YOUR_DEPLOYMENT_ID \
  --region mypurecloud.com \
  --count 4 \
  --message "Warming up!"
```

## Configuration

| Parameter | CLI Flag | Env Var | Default |
|-----------|----------|---------|---------|
| Deployment ID | `--deployment-id` | `GC_DEPLOYMENT_ID` | *(required)* |
| Region | `--region` | `GC_REGION` | *(required)* |
| Warm-Up Message | `--message` | `GC_WARMUP_MESSAGE` | `Warming up!` |
| Escalation Message | `--escalation-message` | `GC_WARMUP_ESCALATION_MESSAGE` | `I want to talk to human agent` |
| Disconnect Message | `--disconnect-message` | `GC_WARMUP_DISCONNECT_MESSAGE` | `Disconnecting now` |
| Count | `--count` | `GC_WARMUP_COUNT` | `1` |
| Origin | `--origin` | `GC_WARMUP_ORIGIN` | `https://localhost` |
| Timeout | `--timeout` | `GC_WARMUP_TIMEOUT` | `30` |

You can also use a `config.yaml` file (set path via `GC_WARMUP_CONFIG_FILE`).

Precedence: Web UI > CLI > Environment Variables > Config File > Defaults

## Running Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```
