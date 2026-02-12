#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory Security Module - HMAC-SHA256 signatures for memory poisoning protection
================================================================================

This module provides cryptographic functions for signing and validating memory entries
to prevent tampering and poisoning attacks.

NOTE: This is a standalone module with a string-based API for ease of use.
The main Entelgia_production_meta.py file has its own bytes-based implementation
for performance. Both are valid but have different interfaces:
- This module: string inputs/outputs (hexdigest)
- Production: bytes inputs/outputs (digest converted to hex when needed)
"""

import hmac
import hashlib


def create_signature(message: str, key: str) -> str:
    """
    Generate HMAC-SHA256 signature for a message.
    
    Args:
        message: The message to sign (plaintext string)
        key: The secret key for signing
        
    Returns:
        Hexadecimal string representation of the signature
        
    Raises:
        ValueError: If message or key is None or empty string
        
    Example:
        >>> signature = create_signature("hello world", "secret_key")
        >>> len(signature)
        64
    """
    if message is None or key is None or message == "" or key == "":
        raise ValueError("Message and key must be non-empty strings")
    
    # Create HMAC-SHA256 signature
    signature = hmac.new(
        key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def validate_signature(message: str, key: str, signature: str) -> bool:
    """
    Validate HMAC-SHA256 signature using constant-time comparison.
    
    Args:
        message: The message to verify
        key: The secret key used for signing
        signature: The signature to validate (hexadecimal string)
        
    Returns:
        True if signature is valid, False otherwise
        
    Example:
        >>> sig = create_signature("hello", "key")
        >>> validate_signature("hello", "key", sig)
        True
        >>> validate_signature("hello", "wrong_key", sig)
        False
    """
    if message is None or key is None or signature is None:
        return False
    
    if message == "" or key == "" or signature == "":
        return False
    
    try:
        # Compute expected signature
        expected_signature = create_signature(message, key)
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(signature, expected_signature)
    except Exception:
        return False
