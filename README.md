# GPU Warm-Up Tool

A Python tool that warms up GPU instances behind a Genesys Cloud Web Messaging deployment by sending a configurable message as new conversations, repeated a configurable number of times.

## Why?

When changes are made to GPU-backed deployments, the first real user conversations can be slow while instances cold-start. This tool pre-warms them so end users get fast responses from the start.

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
| Message | `--message` | `GC_WARMUP_MESSAGE` | `Warming up!` |
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
