# Quick Start: Vercel AI Gateway + GLM-4.6

5-minute setup guide to get started with Vercel AI Gateway and GLM-4.6.

## Prerequisites Checklist

Before you begin, you need:
- [ ] Vercel account (sign up at [vercel.com](https://vercel.com))
- [ ] Zhipu AI account (sign up at [open.bigmodel.cn](https://open.bigmodel.cn))
- [ ] Python 3.11+ installed
- [ ] This DeepAgents project cloned

## Step 1: Get Your API Keys (5 minutes)

### 1.1 Get Vercel AI Gateway API Key

1. **Login to Vercel**: Go to [vercel.com/dashboard](https://vercel.com/dashboard)
2. **Navigate to AI Gateway**: Click the "AI Gateway" tab in the sidebar
3. **Create API Key**:
   - Click "API Keys" in the left sidebar
   - Click "Create key" button
   - Copy the key immediately (shown only once!)
   - Save it somewhere safe temporarily

### 1.2 Get Zhipu AI API Key

1. **Login to Zhipu**: Go to [open.bigmodel.cn](https://open.bigmodel.cn)
2. **Navigate to API Keys**: Click on "API Keys" or "密钥管理"
3. **Create New Key**:
   - Click "Create API Key" or "创建密钥"
   - Copy the key
   - Save it somewhere safe

### 1.3 Add Zhipu to Vercel AI Gateway (IMPORTANT!)

1. **Back in Vercel AI Gateway**: Click "Integrations" in the sidebar
2. **Find Zhipu AI**: Look for "Zhipu AI" or search for it
3. **Add Provider**:
   - Click "Add" next to Zhipu AI
   - Paste your Zhipu API key
   - Toggle "Enabled" to ON
   - Click "Test Key" to verify
   - Click "Save"

## Step 2: Configure Your Project (1 minute)

Edit the `.env` file in your project root:

```bash
# Replace these placeholder values with your actual keys:
AI_GATEWAY_API_KEY=your_vercel_gateway_key_from_step_1.1
ZHIPU_API_KEY=your_zhipu_key_from_step_1.2
```

**Example** (yours will be different):
```bash
AI_GATEWAY_API_KEY=vgw_abc123def456...
ZHIPU_API_KEY=sk_zhipu_xyz789...
```

## Step 3: Test the Integration (30 seconds)

Run the test script:

```bash
python mcp_agent_vercel_glm.py
```

**Expected Output**:
```
================================================================================
TESTING VERCEL AI GATEWAY + GLM-4.6
================================================================================
Initializing Vercel AI Gateway with model: zai/glm-4.6
Vercel AI Gateway model initialized successfully
Sending test query to GLM-4.6 via Vercel AI Gateway...
Response: Hello from GLM-4.6 via Vercel AI Gateway! I'm working correctly...
✅ Test successful!
```

**If you see this** ✅ → You're ready to go! Skip to Step 4.

**If you see errors** ❌ → See troubleshooting below.

## Step 4: Start Using the Agent

### Option A: Use with LangGraph Studio

```bash
# Start LangGraph Studio
langgraph dev
```

Then:
1. Open your browser to the URL shown (usually http://localhost:8123)
2. Select "vercel_glm_agent" from the dropdown
3. Start chatting with GLM-4.6!

### Option B: Use in Python Code

Create a file `test_agent.py`:

```python
import asyncio
from mcp_agent_vercel_glm import agent

async def main():
    # Create the agent
    ai_agent = await agent()

    # Run a query
    result = ai_agent.invoke({
        "messages": [{
            "role": "user",
            "content": "What are the top 3 AI trends in 2025?"
        }]
    })

    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:
```bash
python test_agent.py
```

## Troubleshooting

### Error: "AI_GATEWAY_API_KEY not configured"

**Problem**: The `.env` file still has placeholder values.

**Fix**:
1. Open `.env` file
2. Replace `your_vercel_ai_gateway_key_here` with your actual Vercel key
3. Make sure there are no extra spaces or quotes
4. Save the file
5. Try again

### Error: "Model not found: zai/glm-4.6"

**Problem**: Zhipu AI provider not added to Vercel AI Gateway.

**Fix**:
1. Go to [Vercel AI Gateway Dashboard](https://vercel.com/dashboard)
2. Click "Integrations"
3. Find "Zhipu AI" and click "Add"
4. Enter your Zhipu API key
5. Enable the provider
6. Test the connection
7. Try again

### Error: "Invalid API key"

**Problem**: One of your API keys is incorrect.

**Fix**:
1. **Verify Vercel key**:
   - Go to Vercel Dashboard → AI Gateway → API Keys
   - Create a new key if needed
   - Update `.env` file

2. **Verify Zhipu key**:
   - Go to Zhipu Dashboard
   - Check your API key is active
   - Create new key if needed
   - Update both `.env` and Vercel Integrations

### Error: "Connection timeout"

**Problem**: Network issues or firewall blocking requests.

**Fix**:
1. Check your internet connection
2. Try disabling VPN if using one
3. Check firewall settings
4. Try again in a few minutes

## What's Next?

Now that you have Vercel AI Gateway + GLM-4.6 working:

1. **Read the full guide**: See [VERCEL_AI_GATEWAY_SETUP.md](VERCEL_AI_GATEWAY_SETUP.md) for:
   - Advanced configuration options
   - Cost optimization strategies
   - Performance tuning
   - Best practices

2. **Explore capabilities**:
   - 200K context window: Process huge documents
   - 128K output: Generate comprehensive reports
   - Tool calling: Integrate web scraping, file operations
   - Advanced reasoning: Deep analytical thinking

3. **Monitor usage**:
   - Go to Vercel AI Gateway Dashboard
   - Click "Monitoring"
   - View real-time usage and costs
   - Set up budget alerts

4. **Customize for your needs**:
   - Edit `mcp_agent_vercel_glm.py` to change models
   - Adjust temperature, max_tokens, etc.
   - Add custom tools
   - Modify system prompts

## Key Features You Get

✅ **Unified API**: One interface for all AI models
✅ **Automatic Fallback**: GLM-4.6 → GLM-4.5 → GLM-4.5-Air
✅ **Zero Markup**: Pay exactly what Zhipu charges
✅ **Cost Tracking**: Real-time usage and cost monitoring
✅ **High Availability**: Automatic retries and failover
✅ **Arcade Architecture**: Modular, observable, resilient

## Example Use Cases

### 1. Web Research Agent
```python
result = ai_agent.invoke({
    "messages": [{
        "role": "user",
        "content": "Search for the latest papers on quantum computing and create a summary report. Save it to quantum_research.md"
    }]
})
```

### 2. Code Analysis
```python
result = ai_agent.invoke({
    "messages": [{
        "role": "user",
        "content": "Read all Python files in src/, analyze the code quality, and create a detailed report with recommendations"
    }]
})
```

### 3. Data Extraction
```python
result = ai_agent.invoke({
    "messages": [{
        "role": "user",
        "content": "Scrape the top 10 AI startups from TechCrunch, extract their funding info, and save as JSON"
    }]
})
```

## Performance Tips

1. **Use the right model for the job**:
   - GLM-4.6: Complex reasoning, large documents ($$)
   - GLM-4.5: General tasks ($)
   - GLM-4.5-Air: Simple queries, high volume (¢)

2. **Optimize prompts**:
   - Be specific and concise
   - Use structured output when possible
   - Avoid unnecessary context

3. **Monitor costs**:
   - Set daily budgets in Vercel dashboard
   - Review usage weekly
   - Optimize based on metrics

## Need Help?

- **Setup issues**: Check [VERCEL_AI_GATEWAY_SETUP.md](VERCEL_AI_GATEWAY_SETUP.md)
- **Vercel support**: [vercel.com/support](https://vercel.com/support)
- **Zhipu support**: [open.bigmodel.cn](https://open.bigmodel.cn)

---

**Status**: Ready to use! ✅
**Time to complete**: ~5 minutes
**Difficulty**: Beginner-friendly
