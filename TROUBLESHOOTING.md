# 🔧 Troubleshooting Guide

This guide helps you diagnose and resolve common issues when working with Entelgia.

---

## Table of Contents

- [Installation Issues](#installation-issues)
- [Ollama-Related Problems](#ollama-related-problems)
- [Model Loading Failures](#model-loading-failures)
- [Configuration Errors](#configuration-errors)
- [Runtime Failures](#runtime-failures)
- [Memory and Performance Issues](#memory-and-performance-issues)
- [Testing Issues](#testing-issues)
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

## Model Loading Failures

### Problem: "Model not found" or "phi3 not available"

**Symptoms:**
```
Error: model 'phi3' not found
```

**Solution:**
Pull the required model manually:
```bash
ollama pull phi3
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
ollama pull phi3
```

3. Try an alternative model if phi3 continues to fail:
```bash
# Smaller, faster model
ollama pull phi3:mini

# Or use mistral
ollama pull mistral
```

4. Update your `.env` file to use the alternative model:
```
OLLAMA_MODEL=mistral
```

---

### Problem: Insufficient disk space for model

**Symptoms:**
```
Error: not enough disk space
```

**Solution:**
- phi3 requires ~2.3GB of disk space
- Check available space: `df -h` (Linux/macOS) or `dir` (Windows)
- Free up space or use a smaller model like `phi3:mini`
- Remove unused models: `ollama rm <model-name>`

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
OLLAMA_MODEL=phi3
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

4. Try a faster model if timeouts persist:
```bash
ollama pull phi3:mini
```

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
ollama run phi3 "Hello"
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
This is detected by Fixy (the Observer agent). If it persists:

1. Check Fixy configuration:
```python
config.fixy_every_n_turns = 3  # More frequent intervention
```

2. Increase dream cycle frequency:
```python
config.dream_every_n_turns = 5  # More frequent reflection
```

3. Restart the session to reset context

---

## Memory and Performance Issues

### Problem: High memory usage (RAM)

**Symptoms:**
- System becomes slow
- Out of memory errors

**Solution:**
1. Check model size - larger models need more RAM:
   - `phi3:mini` - ~2GB RAM
   - `phi3` - ~4GB RAM
   - `mistral` - ~4GB RAM

2. Reduce context size:
```python
config.max_turns = 100  # Reduce from default 200
```

3. Close other applications
4. Use a smaller model if your system has limited RAM

---

### Problem: Slow response times

**Symptoms:**
- Each turn takes 30+ seconds
- System feels sluggish

**Solution:**
1. Use a faster model:
```bash
ollama pull phi3:mini
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

## Getting Help

If you've tried the solutions above and still have issues:

### 1. Check Existing Issues
Visit [GitHub Issues](https://github.com/sivanhavkin/Entelgia/issues) to see if others have reported similar problems.

### 2. Gather Information
Before reporting a new issue, collect:
- Python version: `python --version`
- Operating system and version
- Ollama version: `ollama --version`
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

✅ **Use stable models** - `phi3` and `mistral` are well-tested

✅ **Check logs** - Watch Ollama output for errors

✅ **Adequate resources** - Ensure 8GB+ RAM, sufficient disk space

✅ **Stable network** - Required for initial model downloads

✅ **Clean environment** - Use virtual environments to avoid conflicts

---

**Last Updated:** 17 February 2026  
**Version:** 2.3.0
