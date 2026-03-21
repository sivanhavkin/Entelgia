<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">🔧 Troubleshooting Guide</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

This guide helps you diagnose and resolve common issues when working with Entelgia.

---

## Table of Contents

- [Installation Issues](#installation-issues)
- [Ollama-Related Problems](#ollama-related-problems)
- [Grok-Related Problems](#grok-related-problems)
- [OpenAI-Related Problems](#openai-related-problems)
- [Anthropic-Related Problems](#anthropic-related-problems)
- [Model Loading Failures](#model-loading-failures)
- [Configuration Errors](#configuration-errors)
- [Runtime Failures](#runtime-failures)
- [Memory and Performance Issues](#memory-and-performance-issues)
- [Testing Issues](#testing-issues)
- [Web Research Issues](#web-research-issues)
- [Getting Help](#getting-help)

---

## Installation Issues

### Problem: Python version too old

**Symptoms:**
```
SyntaxError: invalid syntax
```

**Solution:**
Entelgia requires Python 3.10 or newer. Check your version:
```bash
python --version
# or
python3 --version
```

If you have an older version, install Python 3.10+ from [python.org](https://www.python.org/downloads/).

---

### Problem: pip install fails with dependency conflicts

**Symptoms:**
```
ERROR: Cannot install package due to conflicting dependencies
```

**Solution:**
1. Create a fresh virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Upgrade pip:
```bash
pip install --upgrade pip
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

---

### Problem: install.py fails on Windows

**Symptoms:**
- Script cannot detect Ollama
- Homebrew commands fail

**Solution:**
Windows requires manual Ollama installation:
1. Download Ollama from [ollama.com/download/windows](https://ollama.com/download/windows)
2. Install it manually
3. Run `install.py` again, or follow manual installation steps in README.md

---

## Ollama-Related Problems

### Problem: "Connection refused" or "Cannot connect to Ollama"

**Symptoms:**
```
requests.exceptions.ConnectionError: Connection refused
```

**Solution:**
1. Check if Ollama is running:
```bash
# Start Ollama service
ollama serve
```

2. Verify Ollama is accessible:
```bash
curl http://localhost:11434/api/version
```

3. If port 11434 is in use, check for conflicting processes:
```bash
# macOS/Linux
lsof -i :11434

# Windows
netstat -ano | findstr :11434
```

---

### Problem: Ollama not found after installation

**Symptoms:**
```
ollama: command not found
```

**Solution:**

**macOS:**
```bash
# If installed via Homebrew
brew install ollama

# Restart your terminal
```

**Linux:**
```bash
# Verify installation
which ollama

# If not found, reinstall
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
- Ensure Ollama is in your PATH
- Restart your terminal/PowerShell
- Try running from a new terminal window

---

## Grok-Related Problems

### Problem: Missing GROK_API_KEY

**Symptoms:**
```
ValueError: grok_api_key must be set when llm_backend is 'grok'
(set GROK_API_KEY in your .env or environment)
```

**Solution:**
1. Obtain an API key from the xAI console:
   - Visit [https://console.x.ai](https://console.x.ai) and sign in with your X (Twitter) account.
   - In the left sidebar, click **API Keys**.
   - Click **Create API Key**, give it a name, and copy the generated key.
2. Add the key to your `.env` file:
```
GROK_API_KEY=xai-xxxxxxxxxxxxxxxxxxxxxxxx
```

3. Restart Entelgia — the key is read at startup.

---

### Problem: Authentication failure / 401 Unauthorized

**Symptoms:**
```
requests.exceptions.HTTPError: 401 Client Error: Unauthorized
```

**Solution:**
1. Verify that `GROK_API_KEY` in your `.env` file is correct and has not expired.
2. Ensure there are no trailing spaces or newline characters in the key value.
3. Regenerate the key at [https://console.x.ai](https://console.x.ai) if necessary and update your `.env` file.

---

### Problem: Grok API endpoint unreachable

**Symptoms:**
```
requests.exceptions.ConnectionError: Failed to establish a new connection
```

**Solution:**
1. Check your internet connection — Grok is a cloud API and requires network access.
2. Verify that the default endpoint is correct in your config (or `.env`):
```
GROK_URL=https://api.x.ai/v1/responses
```
3. Check [https://status.x.ai](https://status.x.ai) for any ongoing xAI service outages.

---

### Problem: Grok model not available

**Symptoms:**
```
requests.exceptions.HTTPError: 404 Client Error: Not Found
```
or the model name is rejected at startup.

**Solution:**
Select a supported Grok model at the interactive startup prompt. The currently available models are:

| Model | Description |
|---|---|
| `grok-4.20-multi-agent` | Multi-agent capable, latest |
| `grok-4-1-fast-reasoning` | Fast reasoning, high performance |

If you are modifying `Config` directly, set the model names to one of the values above:
```python
config.model_socrates = "grok-4-1-fast-reasoning"
config.model_athena   = "grok-4-1-fast-reasoning"
config.model_fixy     = "grok-4-1-fast-reasoning"
```

---

### Problem: Rate limiting or quota exceeded

**Symptoms:**
```
requests.exceptions.HTTPError: 429 Client Error: Too Many Requests
```

**Solution:**
1. Reduce the number of concurrent requests or slow down session turns:
```python
config.llm_timeout = 120  # Allow more time between retries
```
2. Check your xAI account quota at [https://console.x.ai](https://console.x.ai).
3. Upgrade your xAI plan if you consistently hit rate limits during long sessions.

---

### Problem: LLM timeout when using Grok

**Symptoms:**
```
Timeout waiting for LLM response
```

**Solution:**
Cloud API calls may take longer than local Ollama calls on slow connections.

1. Increase the timeout in `Config`:
```python
config.llm_timeout = 120  # seconds (default: 60)
```
2. Check your connection latency to `api.x.ai`.
3. Switch to the faster `grok-4-1-fast-reasoning` model if timeouts are frequent.

---

## OpenAI-Related Problems

### Problem: Missing OPENAI_API_KEY

**Symptoms:**
```
ValueError: openai_api_key must be set when llm_backend is 'openai' (set OPENAI_API_KEY in your .env or environment)
```

**Cause**: You selected the OpenAI backend but `OPENAI_API_KEY` is not set in your `.env` file.

**Solution**:
1. Open your `.env` file (copy from `.env.example` if it does not exist).
2. Add your OpenAI API key:
```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```
3. Save the file and restart Entelgia.

To obtain an API key:
1. Go to [https://platform.openai.com](https://platform.openai.com) and sign in.
2. Click **API keys** in the left sidebar.
3. Click **Create new secret key**, give it a name, and copy the generated key.

### Problem: Authentication failure / 401 Unauthorized

**Symptoms:**
```
requests.exceptions.HTTPError: 401 Client Error: Unauthorized
```

**Cause**: The `OPENAI_API_KEY` in `.env` is invalid or expired.

**Solution**:
1. Verify `OPENAI_API_KEY` is set correctly in `.env` (no extra spaces or newlines).
2. Test the key directly:
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```
3. If the test fails, regenerate the key at [https://platform.openai.com](https://platform.openai.com).

### Problem: OpenAI API endpoint unreachable

**Symptoms:**
```
requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api.openai.com', port=443)
```

**Cause**: No internet connection, or the OpenAI API is temporarily unavailable.

**Solution**:
1. Check your internet connection — OpenAI is a cloud API and requires network access.
2. Verify the endpoint in your `.env` or Config is `https://api.openai.com/v1/chat/completions`.
3. Check the OpenAI status page at [https://status.openai.com](https://status.openai.com).
4. If the issue persists, switch to the Ollama backend for offline operation.

### Problem: OpenAI model not available

**Symptoms:**
```
openai.error.InvalidRequestError: The model 'gpt-4.1' does not exist
```

**Cause**: The selected model is not available on your OpenAI account or tier.

**Solution**:
Select a supported OpenAI model at the interactive startup prompt. The currently available model is:

| Model | Description |
|---|---|
| `gpt-4.1` | Latest GPT-4.1 model |

Ensure your OpenAI account has access to the selected model tier.

### Problem: Rate limiting or quota exceeded

**Symptoms:**
```
openai.error.RateLimitError: You exceeded your current quota
```

**Cause**: Your OpenAI account has hit its API usage limit or rate limit.

**Solution**:
1. Wait a few minutes and try again.
2. Check your usage and limits at [https://platform.openai.com/usage](https://platform.openai.com/usage).
3. Upgrade your OpenAI plan if needed.
4. Alternatively, switch to the Ollama backend (free, local) for unlimited turns.

### Problem: LLM timeout when using OpenAI

**Symptoms:**
```
LLM timeout after N seconds
```

**Cause**: Slow internet connection, high API load, or a very long prompt.

**Solution**:
1. Increase `llm_timeout` in your Config (default: 120 seconds):
```python
config.llm_timeout = 180
```
2. Check your connection latency to `api.openai.com`.

---

## Anthropic-Related Problems

### Problem: Missing ANTHROPIC_API_KEY

**Symptoms:**
```
ValueError: anthropic_api_key must be set when llm_backend is 'anthropic' (set ANTHROPIC_API_KEY in your .env or environment)
```

**Cause**: You selected the Anthropic backend but `ANTHROPIC_API_KEY` is not set in your `.env` file.

**Solution**:
1. Open your `.env` file (copy from `.env.example` if it does not exist).
2. Add your Anthropic API key:
```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
```
3. Save the file and restart Entelgia.

To obtain an API key:
1. Go to [https://console.anthropic.com](https://console.anthropic.com) and sign in.
2. Click **API Keys** in the left sidebar.
3. Click **Create Key**, give it a name, and copy the generated key.

### Problem: Authentication failure / 401 Unauthorized

**Symptoms:**
```
requests.exceptions.HTTPError: 401 Client Error: Unauthorized
```

**Cause**: The `ANTHROPIC_API_KEY` in `.env` is invalid or expired.

**Solution**:
1. Verify `ANTHROPIC_API_KEY` is set correctly in `.env` (no extra spaces or newlines).
2. Test the key directly:
```bash
curl https://api.anthropic.com/v1/models \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
```
3. If the test fails, regenerate the key at [https://console.anthropic.com](https://console.anthropic.com).

### Problem: Anthropic API endpoint unreachable

**Symptoms:**
```
requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api.anthropic.com', port=443)
```

**Cause**: No internet connection, or the Anthropic API is temporarily unavailable.

**Solution**:
1. Check your internet connection — Anthropic is a cloud API and requires network access.
2. Verify the endpoint in your Config is `https://api.anthropic.com/v1/messages`.
3. Check the Anthropic status page at [https://status.anthropic.com](https://status.anthropic.com).
4. If the issue persists, switch to the Ollama backend for offline operation.

### Problem: Anthropic model not available

**Symptoms:**
```
anthropic.BadRequestError: model: claude-opus-4-6 not found
```

**Cause**: The selected Claude model is not available on your Anthropic account or tier.

**Solution**:
Select a supported Anthropic model at the interactive startup prompt. The currently available models are:

| Model | Description |
|---|---|
| `claude-opus-4-6` | Most capable Claude model |
| `claude-sonnet-4-6` | Balanced performance and speed |
| `claude-haiku-4-5` | Fast and lightweight |

Ensure your Anthropic account has access to the selected model tier.

### Problem: Rate limiting or quota exceeded

**Symptoms:**
```
anthropic.RateLimitError: rate_limit_error
```

**Cause**: Your Anthropic account has hit its API usage limit or rate limit.

**Solution**:
1. Wait a few minutes and try again.
2. Check your usage at [https://console.anthropic.com](https://console.anthropic.com).
3. Upgrade your Anthropic plan if needed.
4. Alternatively, switch to the Ollama backend (free, local) for unlimited turns.

### Problem: LLM timeout when using Anthropic

**Symptoms:**
```
LLM timeout after N seconds
```

**Cause**: Slow internet connection, high API load, or a very long prompt.

**Solution**:
1. Increase `llm_timeout` in your Config (default: 120 seconds):
```python
config.llm_timeout = 180
```
2. Check your connection latency to `api.anthropic.com`.
3. Switch to `claude-haiku-4-5` for faster responses.

---

## Model Loading Failures

### Problem: "Model not found" or model not available

**Symptoms:**
```
Error: model 'qwen2.5:7b' not found
```

**Solution:**
Pull the required model manually:
```bash
ollama pull qwen2.5:7b
```

Wait for the download to complete (this may take several minutes depending on your connection).

Verify the model is available:
```bash
ollama list
```

---

### Problem: Model download fails or times out

**Symptoms:**
- Download stalls at certain percentage
- Connection timeout errors

**Solution:**
1. Check your internet connection
2. Retry the download:
```bash
ollama pull qwen2.5:7b
```

3. Try an alternative model if download continues to fail:
```bash
# Use mistral:latest as an alternative
ollama pull mistral:latest
```

> ⚠️ **Note:** Use only models with 7B parameters or larger. Smaller models may execute, but they do not reliably handle the architecture's reflective, memory-heavy, multi-layer reasoning demands.

4. Update your `.env` file to use the alternative model:
```
OLLAMA_MODEL=mistral:latest
```

---

### Problem: Insufficient disk space for model

**Symptoms:**
```
Error: not enough disk space
```

**Solution:**
- `qwen2.5:7b` requires ~5GB of disk space; `llama3.1:8b` requires ~5GB
- Check available space: `df -h` (Linux/macOS) or `dir` (Windows)
- Free up space if needed, or remove unused models: `ollama rm <model-name>`

---

## Configuration Errors

### Problem: Missing .env file

**Symptoms:**
```
Warning: .env file not found
```

**Solution:**
1. Copy the example file:
```bash
cp .env.example .env
```

2. Edit `.env` and configure required settings:
```bash
OLLAMA_MODEL=qwen2.5:7b
MEMORY_SECRET_KEY=your_secret_key_here
```

---

### Problem: Invalid MEMORY_SECRET_KEY

**Symptoms:**
```
ValueError: MEMORY_SECRET_KEY must be at least 32 characters
```

**Solution:**
Generate a secure key using Python:
```python
import secrets
import string

# Generate a 48-character key
key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(48))
print(f"MEMORY_SECRET_KEY={key}")
```

Copy the generated key to your `.env` file.

---

### Problem: Environment variables not loading

**Symptoms:**
- Application uses default values instead of .env values
- Configuration changes have no effect

**Solution:**
1. Verify `.env` file is in the project root directory
2. Check for syntax errors in `.env` (no spaces around `=`)
3. Restart the application after changing `.env`
4. Ensure `python-dotenv` is installed:
```bash
pip install python-dotenv
```

---

## Runtime Failures

### Problem: LLM timeout errors

**Symptoms:**
```
Timeout waiting for LLM response
```

**Solution:**
1. Increase timeout in configuration:
```python
config.llm_timeout = 120  # Increase from default 60 seconds
```

2. Check if Ollama is overloaded:
```bash
# Check running processes
ollama ps
```

3. Restart Ollama service:
```bash
# Stop current instance (Ctrl+C if running in terminal)
# Then start fresh
ollama serve
```

4. Try a faster model if timeouts persist (use a 7B+ model):
```bash
ollama pull qwen2.5:7b
```

> ⚠️ **Note:** Use only models with 7B parameters or larger. Smaller models may execute, but they do not reliably handle the architecture's reflective, memory-heavy, multi-layer reasoning demands.

---

### Problem: "Agent response is empty"

**Symptoms:**
```
Warning: Empty response from agent
```

**Solution:**
1. Check Ollama logs for errors:
```bash
# In the terminal where ollama serve is running
```

2. Verify the model is working:
```bash
ollama run qwen2.5:7b "Hello"
```

3. Check for network issues between Python and Ollama
4. Restart both Ollama and the application

---

### Problem: Memory validation errors

**Symptoms:**
```
ValueError: Memory signature validation failed
```

**Solution:**
1. If you changed `MEMORY_SECRET_KEY`, memory files are now invalid
2. Either:
   - Restore the old key, or
   - Delete old memory files to start fresh:
```bash
# Backup first
mv memories/ memories_backup/

# Start with clean memory
mkdir memories/
```

---

### Problem: Circular reasoning or repetitive dialogue

**Symptoms:**
- Agents repeat the same ideas
- Conversation doesn't progress

**Solution:**
Fixy (the Observer agent) automatically detects and interrupts circular patterns via need-based intervention. If it persists:

1. Increase dream cycle frequency:
```python
config.dream_every_n_turns = 5  # More frequent reflection
```

2. Restart the session to reset context

---

## Memory and Performance Issues

### Problem: High memory usage (RAM)

**Symptoms:**
- System becomes slow
- Out of memory errors

**Solution:**
1. Check model size - larger models need more RAM:
   - `qwen2.5:7b` - ~5GB RAM (recommended minimum)
   - `llama3.1:8b` - ~6GB RAM
   - `mistral:latest` - ~5GB RAM

2. Reduce context size:
```python
config.max_turns = 100  # Reduce from default 200
```

3. Close other applications
4. Ensure you are using a 7B-parameter or larger model; smaller models are not recommended as they do not reliably handle Entelgia's multi-layer reasoning demands

---

### Problem: Slow response times

**Symptoms:**
- Each turn takes 30+ seconds
- System feels sluggish

**Solution:**
1. Use a faster model (while still staying at 7B+):
```bash
ollama pull qwen2.5:7b
```

2. Check CPU usage:
```bash
# macOS/Linux
top

# Windows
taskmgr
```

3. Ensure Ollama isn't running multiple models:
```bash
ollama ps
```

4. Reduce dialogue complexity:
```python
config.max_output_words = 100  # Shorter responses
```

---

### Problem: Disk space fills up quickly

**Symptoms:**
- Low disk space warnings
- Application crashes

**Solution:**
1. Check memory files size:
```bash
du -sh memories/
```

2. Clean old memory files:
```bash
# Backup first
tar -czf memories_backup.tar.gz memories/

# Remove old files
rm -rf memories/*.json
```

3. Limit memory retention in configuration

---

## Testing Issues

### Problem: Tests fail with import errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'pytest'
```

**Solution:**
Install test dependencies:
```bash
pip install pytest pytest-mock
```

---

### Problem: Tests fail with "Connection refused"

**Symptoms:**
Tests can't connect to Ollama

**Solution:**
1. Ensure Ollama is running before tests:
```bash
ollama serve
```

2. Or mock Ollama in tests (see test files for examples)

---

### Problem: Test files not found

**Symptoms:**
```
ERROR: file or directory not found: test_*.py
```

**Solution:**
Run tests from project root:
```bash
cd /path/to/Entelgia
python -m pytest tests/
```

---

## Web Research Issues

### Problem: `ImportError: No module named 'bs4'`

**Symptoms:**
```
ImportError: No module named 'bs4'
```

**Solution:** Install `beautifulsoup4`:
```bash
pip install beautifulsoup4>=4.12.0
```

Or reinstall all dependencies:
```bash
pip install -r requirements.txt
```

---

### Problem: Web search returns no results

**Symptoms:**
`maybe_add_web_context` returns an empty string even for research-intent queries.

**Possible causes & solutions:**
- **No internet connection** — the module fails gracefully when offline; this is expected behaviour.
- **DuckDuckGo blocked or rate-limited** — try again later or check connectivity.
- **Query does not contain trigger keywords** — ensure the message contains one of:
  `latest`, `recent`, `research`, `news`, `current`, `today`, `web`, `find`, `search`, `paper`, `study`, `article`, `published`, `updated`, `new`, `trend`, `report`, `source`.
- **Per-query cooldown active** — if the same `seed_text` already triggered a search within the last 5 turns, the search is suppressed. Wait a few turns or call `clear_trigger_cooldown()` in tests.

---

### Problem: Some pages are always skipped (no text extracted)

**Symptoms:**
Certain URLs consistently return empty `title` and `text` even with a valid network connection.

**Explanation:**
URLs that returned HTTP **403 Forbidden** or **404 Not Found** are permanently added to
the `_failed_urls` blacklist for the lifetime of the process.  This is intentional —
it prevents repeated failed requests to pages that have blocked the scraper or do not
exist.

If you need to retry a blacklisted URL (e.g. in a long-running process or test), call:

```python
from entelgia.web_tool import clear_failed_urls
clear_failed_urls()
```

---

### Problem: Web research is slow or times out

**Symptoms:**
Noticeably slower response when web research is triggered.

**Solution:**
Each HTTP request has a 10-second timeout.  In slow network conditions fetching
several pages can take up to ~60 seconds.  This is by design — the timeout prevents
indefinite blocking.  You can reduce `max_results` in the `maybe_add_web_context`
call to speed things up:

```python
context = maybe_add_web_context(user_message, max_results=2)
```

---

### Problem: External knowledge not stored in database

**Symptoms:**
High-credibility sources (score > 0.6) are not appearing in the `external_knowledge` table.

**Solution:**
Memory persistence is opt-in.  Pass a `db_path` argument:

```python
from entelgia.web_research import maybe_add_web_context

context = maybe_add_web_context(
    user_message="latest AI research",
    db_path="entelgia_memory.db",
)
```

When `db_path=None` (the default) memory storage is silently skipped.

---

## Getting Help

If you've tried the solutions above and still have issues:

### 1. Check Existing Issues
Visit [GitHub Issues](https://github.com/sivanhavkin/Entelgia/issues) to see if others have reported similar problems.

### 2. Gather Information
Before reporting a new issue, collect:
- Python version: `python --version`
- Operating system and version
- LLM backend in use: Ollama or Grok
- Ollama version (if applicable): `ollama --version`
- Grok model name (if applicable)
- Error messages (full traceback)
- Steps to reproduce

### 3. Report the Issue
Create a new issue using the bug report template:
- Go to [New Issue](https://github.com/sivanhavkin/Entelgia/issues/new/choose)
- Select "Bug Report"
- Fill in all sections with details

### 4. Security Issues
For security-related issues, follow the [Security Policy](SECURITY.md) and report privately.

---

## Experimental Nature

Remember that Entelgia is a **Research Hybrid** project:
- Some behaviors are experimental and may change
- Not all edge cases are handled
- The system is designed for research and exploration
- Not recommended for safety-critical applications

See the [README](README.md#-project-status) for more about the "Research Hybrid" status.

---

## Common Success Patterns

These patterns help ensure Entelgia works reliably:

✅ **Start fresh** - When in doubt, restart Ollama and the application

✅ **Use stable models** - `qwen2.5:7b`, `llama3.1:8b`, and `mistral:latest` are well-tested and recommended (7B+ required)

✅ **Check logs** - Watch Ollama output for errors

✅ **Adequate resources** - Ensure 8GB+ RAM, sufficient disk space

✅ **Stable network** - Required for initial model downloads

✅ **Clean environment** - Use virtual environments to avoid conflicts

---

**Last Updated:** 07 March 2026  
**Version:** 4.0.0
