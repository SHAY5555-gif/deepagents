# Railway Deployment Guide - ZAMAR Agent

## Overview

This guide explains how to deploy the ZAMAR (Cerebras) song lyrics agent to Railway from the terminal.

## Prerequisites

1. **Railway CLI installed**
   ```bash
   npm install -g @railway/cli
   ```

2. **Railway account** - Sign up at [railway.app](https://railway.app)

3. **Login to Railway**
   ```bash
   railway login
   ```

## Project Structure

```
deepagents/
├── agents/
│   └── zamar/
│       └── cerebras_zamar.py    # Main ZAMAR agent
├── Dockerfile                    # Docker configuration
├── requirements.txt              # Python dependencies
└── pyproject.toml               # Package configuration
```

## Deployment Steps

### Step 1: Link to Railway Project

```bash
cd /path/to/deepagents
railway link
```

Select your project and service when prompted.

### Step 2: Deploy

```bash
railway up --service deepagents-langgraph --detach
```

The `--detach` flag runs the deployment in the background.

### Step 3: Verify Deployment

```bash
# Check available assistants
curl -X POST https://deepagents-langgraph-production.up.railway.app/assistants/search \
  -H "Content-Type: application/json" \
  -H "x-api-key: demo-token" \
  -d '{}'
```

## Available Agents

| Agent Name | Description | Assistant ID |
|------------|-------------|--------------|
| `cerebras_zamar` | Song lyrics finder using Cerebras GLM-4.6 | `1722d8b3-0529-59e0-b26b-86e0e0af108b` |
| `glm_cerebras` | General purpose Cerebras agent | `fca8fa72-703e-55c1-a92e-e92f1908c947` |
| `grok_bright_data` | Web scraping with Bright Data | `19f11ab0-818a-5a0f-a22c-860f94d7c946` |
| `basic_no_mcp` | Basic agent without MCP tools | `f3d0197f-ba58-5ea8-bda9-63883e91cf71` |

## API Usage

### Base URL
```
https://deepagents-langgraph-production.up.railway.app
```

### Authentication
```
Header: x-api-key: demo-token
```

### Create a Thread

```bash
curl -X POST https://deepagents-langgraph-production.up.railway.app/threads \
  -H "x-api-key: demo-token" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Response:
```json
{
  "thread_id": "abc123-...",
  "created_at": "2025-12-03T..."
}
```

### Send a Message (Streaming)

```bash
curl -X POST https://deepagents-langgraph-production.up.railway.app/threads/{THREAD_ID}/runs/stream \
  -H "x-api-key: demo-token" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "messages": [
        {
          "type": "human",
          "content": "Find lyrics for a song by artist name"
        }
      ]
    },
    "assistant_id": "cerebras_zamar",
    "stream_mode": ["messages-tuple", "values"],
    "config": {
      "recursion_limit": 100
    }
  }'
```

## Environment Variables

Make sure these are set in Railway:

| Variable | Description |
|----------|-------------|
| `CEREBRAS_API_KEY` | Cerebras API key for GLM-4.6 |
| `GENIUS_ACCESS_TOKEN` | Genius API token for song search |
| `LANGSMITH_API_KEY` | LangSmith API key (optional) |

## Dockerfile Configuration

The Dockerfile defines which agents are available via the `LANGSERVE_GRAPHS` environment variable:

```dockerfile
ENV LANGSERVE_GRAPHS='{"cerebras_zamar": "/deps/__outer_default/agents/zamar/cerebras_zamar.py:agent", ...}'
```

### Adding a New Agent

1. Create the agent file in `agents/` folder
2. Ensure it has an `async def agent()` function
3. Add it to `LANGSERVE_GRAPHS` in the Dockerfile
4. Redeploy with `railway up`

## Monitoring

### View Logs
```bash
railway logs --service deepagents-langgraph
```

### Check Service Status
```bash
railway status
```

## Troubleshooting

### 502 Error
- Service is restarting or building
- Wait 2-3 minutes and try again

### Agent Not Found
- Check if the agent is in `LANGSERVE_GRAPHS`
- Verify the file path is correct
- Redeploy after fixing

### Build Failures
- Check the build logs in Railway dashboard
- Verify all dependencies are in `requirements.txt`

## Quick Reference

```bash
# Deploy
railway up --service deepagents-langgraph --detach

# View logs
railway logs --service deepagents-langgraph

# Check status
railway status

# Open dashboard
railway open
```

## Links

- **Railway Dashboard**: https://railway.app/dashboard
- **Build Logs**: Available in Railway dashboard under Deployments
- **API Endpoint**: https://deepagents-langgraph-production.up.railway.app
