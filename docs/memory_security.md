<img src="../Assets/entelgia-logo.png" alt="Entelgia Logo" width="120"/>

# Memory Security

## Overview

Entelgia implements cryptographic signatures for all memory entries to prevent tampering and poisoning attacks. Each memory (both STM and LTM) is signed with HMAC-SHA256, ensuring integrity verification on every read operation.

## Features

### 🔐 Cryptographic Signatures
- **HMAC-SHA256** signatures for all memory entries
- **Constant-time comparison** using `hmac.compare_digest()` to prevent timing attacks
- **JSON serialization** for robust handling of special characters

### 🛡️ Poisoning Prevention
- Invalid signatures are detected and logged
- Tampered memories are automatically filtered out
- Prevents forged or modified memories from being used

### 🔑 Key Management
- Secret key loaded from `MEMORY_SECRET_KEY` environment variable
- Development fallback key with clear warnings
- Easy rotation without code changes

### ↔️ Backward Compatibility
- Legacy memories without signatures are still accepted
- Graceful migration path for existing databases
- No breaking changes to existing functionality

## Setup

### 1. Generate a Secure Key

```bash
# Generate a random 32-byte key (64 hex characters)
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Set Environment Variable

**For Development:**
```bash
# Create .env file from template
cp .env.example .env

# Edit .env and set your key
echo "MEMORY_SECRET_KEY=your-generated-key-here" >> .env
```

**For Production:**
```bash
# Set environment variable
export MEMORY_SECRET_KEY="your-secure-random-key-here"

# Or add to your systemd service, Docker compose, etc.
```

### 3. Run Entelgia

```bash
python Entelgia_production_meta.py
```

## Security Guarantees

### What is Protected

✅ **Memory Content** - The actual content of memories  
✅ **Topics** - Memory topics/categories  
✅ **Emotions** - Emotional tags  
✅ **Timestamps** - When memories were created  

### What is Detected

🚨 **Content Tampering** - Any modification to protected fields  
🚨 **Database Manipulation** - Direct database edits are detected  
🚨 **Memory Poisoning** - Forged memories injected externally  

### What is NOT Protected

⚠️ **Metadata Fields** - Fields like importance, layer, source are not signed  
⚠️ **Key Compromise** - If the secret key is leaked, all signatures can be forged  
⚠️ **Replay Attacks** - Old valid memories can be replayed (timestamps are signed but not checked)  

## Architecture

### STM (Short-Term Memory)
- Signatures stored in `_signature` field within JSON
- Validated when loaded (future enhancement)
- Signature computed before adding `_signature` field

### LTM (Long-Term Memory)
- Signatures stored in `signature_hex` column in SQLite
- Validated on every read operation via `ltm_recent()`
- Invalid memories are filtered out and logged

### Signature Payload

LTM signatures use a JSON payload with consistent key ordering:

```json
{
  "content": "memory content",
  "emotion": "emotion tag or empty string",
  "topic": "topic or empty string", 
  "ts": "ISO 8601 timestamp"
}
```

**Critical:** `sort_keys=True` ensures consistent ordering between signing and validation.

## Examples

### Creating Signed Memory

```python
from Entelgia_production_meta import MemoryCore

memory = MemoryCore("entelgia_memory.sqlite")

# Memory is automatically signed
mem_id = memory.ltm_insert(
    agent="socrates",
    layer="conscious",
    content="I think therefore I am",
    topic="philosophy",
    emotion="contemplative"
)
```

### Retrieving with Validation

```python
# All memories are validated on retrieval
memories = memory.ltm_recent("socrates", limit=10)

# Invalid memories are automatically filtered out
# Check logs for security warnings
```

### Detecting Tampering

If a memory is tampered with in the database:

```python
# This memory will be filtered out on next read
# Warning logged:
# ⚠️  SECURITY: Invalid signature detected for memory abc-123. 
# Memory skipped (forgotten). This may indicate tampering or poisoning attempt.
```

## Monitoring

### Log Messages

**Success Messages:**
```
✓ MEMORY_SECRET_KEY loaded from environment (production mode)
```

**Warning Messages:**
```
⚠️  Using insecure development MEMORY_SECRET_KEY! 
Set MEMORY_SECRET_KEY environment variable for production use.
```

**Security Alerts:**
```
⚠️  SECURITY: Invalid signature detected for memory {id}. 
Memory skipped (forgotten). This may indicate tampering or poisoning attempt.
```

### Metrics to Monitor

- Number of security warnings (should be 0 in production)
- Memory validation failures (indicates tampering attempts)
- Signature verification time (should be < 1ms per memory)

## Best Practices

### Key Management

1. **Never commit keys to version control**
2. **Use different keys for dev/staging/production**
3. **Rotate keys periodically** (requires re-signing all memories)
4. **Use secrets management** (HashiCorp Vault, AWS Secrets Manager, etc.)

### Security

1. **Monitor security logs** for tampering attempts
2. **Use strong random keys** (32+ bytes)
3. **Restrict database access** to prevent direct manipulation
4. **Consider encryption at rest** for additional protection

### Operations

1. **Backup before key rotation** - old memories become unreadable
2. **Test in staging** before production deployment
3. **Plan migration** for legacy memories if needed

## Troubleshooting

### "Invalid signature detected" Warnings

**Cause:** Memory was tampered with or key changed

**Solutions:**
1. Check if `MEMORY_SECRET_KEY` changed
2. Verify database has not been manually edited
3. Check for disk corruption
4. Review access logs for unauthorized access

### Using Development Key Warning

**Cause:** `MEMORY_SECRET_KEY` not set in environment

**Solution:**
```bash
export MEMORY_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

### All Memories Showing as Invalid

**Cause:** Secret key changed after memories were created

**Solution:**
1. Restore original `MEMORY_SECRET_KEY`
2. Or accept that old memories cannot be validated
3. Or re-sign all memories with new key (requires custom script)

## Implementation Details

### Files

- **`memory_security.py`** - Core signature functions
- **`Entelgia_production_meta.py`** - Integration with MemoryCore
- **`.env.example`** - Environment variable template

### Functions

```python
# Create signature
signature = memory_security.create_signature(message, key)

# Validate signature  
is_valid = memory_security.validate_signature(message, key, signature)
```

### Database Schema

```sql
ALTER TABLE memories ADD COLUMN signature_hex TEXT DEFAULT NULL;
```

## Future Enhancements

- [ ] STM signature validation on load
- [ ] Automatic key rotation support
- [ ] Migration tool for re-signing memories
- [ ] Timestamp validation to prevent replay attacks
- [ ] Support for multiple key versions
- [ ] Audit log for all validation failures

## References

- [HMAC-SHA256 Specification (RFC 2104)](https://tools.ietf.org/html/rfc2104)
- [Python hmac module](https://docs.python.org/3/library/hmac.html)
- [Constant-Time Comparison](https://codahale.com/a-lesson-in-timing-attacks/)
