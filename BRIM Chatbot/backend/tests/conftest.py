"""
Test-wide defaults.

The suite creates dozens of accounts and chat turns in a few seconds, which would trip the
production rate limiter. It is disabled here and exercised explicitly in test_security.py, which
turns it back on for its own requests.
"""

import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
