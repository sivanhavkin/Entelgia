<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">❓ Frequently Asked Questions (FAQ)</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

## Table of Contents

- [General Questions](#general-questions)
- [Installation & Setup](#installation--setup)
- [Architecture & Concepts](#architecture--concepts)
- [Usage & Operation](#usage--operation)
- [Memory & State Management](#memory--state-management)
- [Configuration & Customization](#configuration--customization)
- [Performance & Requirements](#performance--requirements)
- [Troubleshooting](#troubleshooting)
- [Development & Contributing](#development--contributing)

---

## General Questions

### What is Entelgia?

Entelgia is an experimental multi-agent AI architecture designed to explore persistent identity, internal conflict dynamics, and emergent behavioral regulation through shared long-term memory and structured dialogue. Unlike stateless chatbot systems, Entelgia maintains an evolving internal state across sessions, enabling continuity of identity, memory persistence, and more coherent reflective behavior over time.

### What does "Entelgia" mean?

Entelgia is derived from philosophical concepts related to entelechy (the realization of potential) and intelligence, representing a system that evolves and actualizes its capabilities through continuous dialogue and reflection.

### Is Entelgia production-ready?

Entelgia is currently a **Research Hybrid** project. While it has a stable codebase (v2.5.0) with comprehensive testing and CI/CD pipelines, it is primarily designed as an experimental platform for exploring consciousness-inspired AI architectures rather than a production service.

### Who should use Entelgia?

Entelgia is ideal for:
- AI researchers exploring multi-agent systems
- Cognitive science enthusiasts interested in consciousness models
- Developers studying emergent behavior in AI
- Anyone curious about persistent AI identity and memory systems

### What makes Entelgia different from other chatbot systems?

Unlike typical chatbots:
- **Persistent Identity**: Maintains evolving state across sessions
- **Internal Conflict**: Models competing internal drives (Id/Ego/Superego dynamics)
- **Memory Continuity**: Long-term memory enables identity persistence
- **Emergent Regulation**: Internal conflict produces behavioral coherence rather than external censorship
- **Multi-Agent Dialogue**: Three agents with distinct personas engage in structured conversations

---

## Installation & Setup

### What are the system requirements?

- **Python**: 3.10 or newer
- **Ollama**: Local LLM runtime
- **Models**: At least one supported model (`phi3`, `mistral`, etc.)
- **RAM**: 8GB+ recommended (16GB+ for larger models)
- **OS**: macOS, Linux, or Windows (with WSL2)

### How do I install Entelgia?

The recommended method is using the automated installer:

```bash
git clone https://github.com/sivanhavkin/Entelgia.git
cd Entelgia
python scripts/install.py
```

The installer will:
1. Detect and install Ollama (macOS via Homebrew)
2. Pull the `phi3` model automatically
3. Create `.env` configuration from template
4. Generate secure `MEMORY_SECRET_KEY`
5. Install Python dependencies

For manual installation, see the [README.md](README.md) guide.

### Why do I need Ollama?

Entelgia requires a local LLM runtime for agent responses. Ollama provides:
- Local execution (no external API calls)
- Multiple model support
- Easy model management
- Privacy and security
- No API costs

### Can I use OpenAI or other LLM providers?

Currently, Entelgia is designed to work with Ollama for local LLM execution. While theoretically adaptable to other providers, this would require significant code modifications and is not officially supported.

### What is the MEMORY_SECRET_KEY?

The `MEMORY_SECRET_KEY` is a cryptographic key used to sign and verify long-term memory entries, preventing tampering. The installer generates a secure 48-character key automatically. This ensures memory integrity across sessions.

---

## Architecture & Concepts

### What are the three agents?

1. **Socrates** — The Questioner
   - Reflective and dialectical inquiry
   - Structures meaning through questions
   - Challenges assumptions

2. **Athena** — The Synthesizer
   - Integrative and creative
   - Emotional coherence
   - Perspective shifts and synthesis

3. **Fixy** — The Observer
   - Meta-cognitive monitoring
   - Corrective feedback
   - Need-based interventions

### What is the CoreMind system?

The CoreMind is Entelgia's modular architecture consisting of:
- **Conscious**: Reflective narrative construction
- **Memory**: Persistent identity continuity
- **Emotion**: Affective weighting & regulation
- **Language**: Dialogue-driven cognition
- **Behavior**: Goal-oriented response shaping
- **Observer**: Meta-level monitoring & correction

### How does memory work in Entelgia?

Entelgia uses a two-layer memory model:

**Short-Term Memory (STM)**:
- Stored in JSON
- Session-local
- Volatile
- High-frequency updates
- Recent dialogue context

**Long-Term Memory (LTM)**:
- Persisted across sessions
- Cryptographically signed (HMAC-SHA256)
- Identity-defining memories
- Selective retrieval based on relevance

### What are "drives" in the context of Entelgia?

Drives are internal state vectors that influence agent behavior, modeling:
- **Id**: Impulsive, desire-driven tendencies
- **Ego**: Reality-testing and practical considerations
- **Superego**: Moral and ethical constraints

These competing drives create internal tension that shapes agent responses and enables emergent regulation.

### What is Fixy's role?

Fixy is the meta-observer that:
- Monitors dialogue patterns
- Detects circular reasoning or repetition
- Intervenes only when needed (not on a fixed schedule)
- Provides corrective feedback
- Helps maintain dialogue quality

In enhanced mode, Fixy uses intelligent detection rather than scheduled checks.

### What is "enhanced mode"?

Enhanced mode (v2.2.0+) provides:
- **Dynamic speaker selection** (vs. simple ping-pong)
- **6 seed strategies** for dialogue variety
- **Context-aware prompts** with 8 turns + 6 thoughts + 5 memories
- **Intelligent Fixy** with need-based interventions
- **Rich personas** with traits and speech patterns

---

## Usage & Operation

### How do I run Entelgia?

After installation:

```bash
# Start Ollama service
ollama serve

# Run the quick demo (10 turns, ~2 minutes)
python examples/demo_enhanced_dialogue.py

# Or run the full system (30 minutes)
python Entelgia_production_meta.py
```

### What happens during a typical session?

1. System initializes with agent personas and memory
2. Dialogue begins with dynamic speaker selection
3. Selected agent generates a response based on:
   - Current dialogue context
   - Relevant memories (STM + LTM)
   - Internal drives and persona
4. Response is logged and memory is updated
5. Fixy may intervene if needed
6. Dream/reflection cycles occur periodically
7. Process continues for configured number of turns

### How long does a session take?

- **Demo mode** (`demo_enhanced_dialogue.py`): ~2 minutes (10 turns)
- **Full session** (`Entelgia_production_meta.py`): ~30 minutes (default 200 turns)
- Duration depends on:
  - Number of turns configured
  - LLM response time
  - Model size and system performance

### Can I interrupt a running session?

Yes, use `Ctrl+C` to gracefully interrupt. The system will save memory state before exiting (depending on implementation).

### How do I view the dialogue output?

Dialogue output is displayed in the terminal in real-time, showing:
- Agent name
- Response text
- Internal thoughts (for Athena)
- Metadata (turn number, timestamp, etc.)

---

## Memory & State Management

### Where is memory stored?

- **Short-term memory**: Typically in-memory JSON during session
- **Long-term memory**: Persisted to disk (format depends on configuration)
- **Configuration**: `.env` file specifies `MEMORY_SECRET_KEY` for signing

### How is memory secured?

Memory entries use HMAC-SHA256 signatures to:
- Prevent tampering
- Ensure integrity
- Verify authenticity
- Detect unauthorized modifications

The cryptographic key (`MEMORY_SECRET_KEY`) must be kept secure.

### Can I reset memory?

Yes, memory can be reset by clearing the long-term memory storage. This creates a fresh identity state. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for instructions.

### How does memory affect agent behavior?

Memory enables:
- **Continuity**: Agents remember past conversations
- **Learning**: Behavioral patterns evolve over time
- **Identity**: Persistent personality traits
- **Context**: Relevant past experiences inform responses

### What happens if memory becomes corrupted?

If memory signatures fail validation:
- System detects tampering
- Corrupted entries are rejected
- Warning is logged
- System can continue with valid memories or reset

---

## Configuration & Customization

### How do I configure Entelgia?

Configuration is done through:
1. **`.env` file**: Environment variables (API keys, secrets)
2. **`Config` class**: Runtime parameters in code

Key settings include:
- `max_output_words`: LLM response length guidance (default: 150)
- `llm_timeout`: Seconds to wait for LLM (default: 60)
- `max_turns`: Maximum dialogue turns (default: 200)
- `dream_every_n_turns`: Dream cycle frequency (default: 7)

### Can I change agent personas?

Yes! Agent personas are defined in:
- Legacy mode: `Entelgia_production_meta.py`
- Enhanced mode: `entelgia/enhanced_personas.py`

You can modify personality traits, speech patterns, and behavioral tendencies.

### Can I add more agents?

Yes, but this requires code modifications:
- Define new agent persona
- Add to agent initialization
- Update speaker selection logic
- Ensure memory system accommodates new agent

This is an advanced customization not officially supported.

### Can I use different LLM models?

Yes! Entelgia supports any Ollama-compatible model. Specify the model in configuration:
- `phi3` (default, recommended)
- `mistral`
- `llama2`
- Other models available through Ollama

Different models will produce different dialogue qualities and require varying resources.

### How do I adjust response length?

Response length is controlled via LLM prompt instruction (not truncation):

```python
config.max_output_words = 150  # Guidance for LLM
```

Starting from v2.2.0, responses are **never truncated** - the LLM is guided to produce concise responses naturally.

---

## Performance & Requirements

### Why does Entelgia run slowly?

Common causes:
- **Large model**: Bigger models take longer to generate responses
- **Limited RAM**: Insufficient memory causes swapping
- **CPU-only inference**: GPU acceleration significantly faster
- **Network issues**: If Ollama service is remote
- **First run**: Model loading takes extra time

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for optimization tips.

### Can I run Entelgia on a laptop?

Yes! Entelgia can run on modern laptops with:
- 8GB+ RAM for smaller models (`phi3`)
- 16GB+ RAM recommended for larger models
- SSD storage for faster model loading
- Recent CPU (GPU optional but helpful)

### Does Entelgia require internet?

No! Entelgia runs entirely locally:
- Ollama provides local LLM inference
- No external API calls
- Complete privacy and offline operation
- (Internet needed only for initial installation)

### How much disk space does Entelgia need?

- **Entelgia code**: < 50MB
- **Python dependencies**: ~100-200MB
- **Ollama models**: 2-8GB each (depends on model)
- **Memory storage**: Grows over time (typically < 100MB)

Total: Plan for 3-10GB depending on models installed.

---

## Troubleshooting

### "Connection refused" error when running Entelgia

**Cause**: Ollama service is not running.

**Solution**:
```bash
ollama serve
```

Keep this running in a separate terminal, then run Entelgia in another terminal.

### "Model not found" error

**Cause**: Required LLM model not downloaded.

**Solution**:
```bash
ollama pull phi3
```

Or use the model name specified in your configuration.

### Python dependency conflicts

**Cause**: Conflicting package versions.

**Solution**:
1. Create fresh virtual environment
2. Upgrade pip
3. Install from requirements.txt

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed steps.

### Memory validation fails

**Cause**: Incorrect `MEMORY_SECRET_KEY` or corrupted memory files.

**Solution**:
- Ensure `.env` file has correct `MEMORY_SECRET_KEY`
- If key is lost, reset memory (will lose history)
- Check for file system corruption

### Tests fail

**Cause**: Various possible issues.

**Solution**:
```bash
# Run enhanced dialogue tests
python tests/test_enhanced_dialogue.py

# Run security tests
pytest tests/test_memory_security.py -v
```

Check test output for specific errors. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for test-specific guidance.

### Where can I get more help?

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed solutions
2. Review [README.md](README.md) for setup instructions
3. Consult [SPEC.md](SPEC.md) for architectural details
4. Open an issue on GitHub with:
   - Error messages
   - System information
   - Steps to reproduce

---

## Development & Contributing

### How can I contribute to Entelgia?

See [Contributing.md](Contributing.md) for guidelines on:
- Code contributions
- Bug reports
- Feature requests
- Documentation improvements

### What is the testing strategy?

Entelgia has comprehensive test coverage:
- **5 enhanced dialogue tests**: Speaker selection, seed variety, context enrichment, Fixy interventions, persona formatting
- **19 memory security tests**: Signature creation, validation, security properties
- **CI/CD pipeline**: Automated quality checks on every commit

Run tests:
```bash
python tests/test_enhanced_dialogue.py
pytest tests/test_memory_security.py -v
```

### What coding standards does Entelgia follow?

- **Python 3.10+** syntax
- **Black** for code formatting
- **Flake8** for linting
- **MyPy** for type checking
- **Security**: Bandit and Safety scans
- **No emojis/Unicode in logger messages** (Windows compatibility)

### How is the project structured?

```
Entelgia/
├── Entelgia_production_meta.py    # Main system file
├── entelgia/                       # Enhanced dialogue package
│   ├── dialogue_engine.py
│   ├── enhanced_personas.py
│   ├── context_manager.py
│   └── fixy_interactive.py
├── docs/                           # Documentation
├── tests/                          # Test suite
├── install.py                      # Automated installer
├── demo_enhanced_dialogue.py       # Quick demo
└── README.md                       # Main documentation
```

### Where can I learn more about the theory behind Entelgia?

- **[whitepaper.md](whitepaper.md)**: Complete architectural and theoretical foundation
- **[SPEC.md](SPEC.md)**: Detailed system specification
- **[entelgia_demo.md](entelgia_demo.md)**: See the system in action

### Is Entelgia open source?

Yes! Entelgia is released under the MIT License. See [LICENSE](LICENSE) for details.

### How can I stay updated?

- Watch the GitHub repository for updates
- Check [Changelog.md](Changelog.md) for version history
- Follow semantic versioning: Major.Minor.Patch (e.g., v2.5.0)

---

## Additional Resources

- 📘 **[README.md](README.md)** - Quick start and overview
- 📄 **[SPEC.md](SPEC.md)** - System specification
- 📖 **[whitepaper.md](whitepaper.md)** - Theoretical foundation
- 🔧 **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Detailed problem-solving
- 📜 **[Changelog.md](Changelog.md)** - Version history
- 🤝 **[Contributing.md](Contributing.md)** - Contribution guidelines
- 🛡️ **[SECURITY.md](SECURITY.md)** - Security policy
- ⚖️ **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** - Community standards

---

**Last Updated**: Version 2.5.0
