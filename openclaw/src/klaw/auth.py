"""
KLAW License Authentication — Verify subscription before paid tier access.

License flow:
    1. User signs up at checkout link → Stripe subscription
    2. Webhook creates license key in Supabase
    3. User sets KLAW_LICENSE_KEY=klaw_live_abc123
    4. KLAW verifies against Supabase RPC on first paid-tier use
    5. Caches result locally for 24 hours

Free tiers (template, local) ALWAYS work without a license.
Paid tiers (cheap, mid, premium) require an active license.
"""

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

# Supabase project for license verification
SUPABASE_URL = "https://cxxigmzglhuwhaiuosag.supabase.co"
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN4eGlnbXpnbGh1d2hhaXVvc2FnIi"
    "wicm9sZSI6ImFub24iLCJpYXQiOjE3MzU3NzA4NjQsImV4cCI6MjA1MTM0Njg2NH0."
    "d0GDMmFIySIF0KOr_VPrspLDsHH3MF9u3mb0V0M3LJY"
)

# Cache settings
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours
CACHE_FILE = Path.home() / ".klaw" / "license_cache.json"


class LicenseStatus:
    """Result of a license check."""
    def __init__(self, valid: bool, tier: str = "free", status: str = "none",
                 email: str = "", error: str = "", cached: bool = False):
        self.valid = valid
        self.tier = tier
        self.status = status
        self.email = email
        self.error = error
        self.cached = cached

    @property
    def can_use_paid(self) -> bool:
        return self.valid and self.tier == "pro"

    def __repr__(self):
        return f"LicenseStatus(valid={self.valid}, tier={self.tier}, status={self.status})"


def _load_cache() -> dict:
    """Load cached license verification."""
    if not CACHE_FILE.exists():
        return {}
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        # Check TTL
        if time.time() - data.get("verified_at", 0) < CACHE_TTL_SECONDS:
            return data
    except Exception:
        pass
    return {}


def _save_cache(license_key: str, result: dict):
    """Cache a license verification result."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cache = {
        "license_key_hash": _hash_key(license_key),
        "verified_at": time.time(),
        **result,
    }
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _hash_key(key: str) -> str:
    """Hash license key for cache (don't store plaintext)."""
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _verify_remote(license_key: str) -> dict:
    """Verify license key against Supabase RPC."""
    payload = json.dumps({"p_license_key": license_key}).encode("utf-8")

    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/verify_klaw_license",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"valid": False, "error": f"http_{e.code}", "detail": body}
    except Exception as e:
        return {"valid": False, "error": f"network_error: {e}"}


def verify_license(license_key: str = None) -> LicenseStatus:
    """
    Verify a KLAW license key.

    Checks (in order):
        1. Local cache (if < 24 hours old)
        2. Supabase RPC verification
        3. Caches result

    Args:
        license_key: The key to verify. If None, reads from KLAW_LICENSE_KEY env var.

    Returns:
        LicenseStatus with .valid, .tier, .can_use_paid, etc.
    """
    key = license_key or os.environ.get("KLAW_LICENSE_KEY", "")

    if not key:
        return LicenseStatus(
            valid=False,
            error="no_license_key",
            tier="free",
        )

    # Check cache first
    cache = _load_cache()
    if cache and cache.get("license_key_hash") == _hash_key(key):
        if cache.get("valid"):
            return LicenseStatus(
                valid=True,
                tier=cache.get("tier", "pro"),
                status=cache.get("status", "active"),
                email=cache.get("email", ""),
                cached=True,
            )
        else:
            return LicenseStatus(
                valid=False,
                error=cache.get("error", "cached_invalid"),
                tier="free",
                cached=True,
            )

    # Remote verification
    result = _verify_remote(key)

    # Cache the result
    _save_cache(key, result)

    if result.get("valid"):
        return LicenseStatus(
            valid=True,
            tier=result.get("tier", "pro"),
            status=result.get("status", "active"),
            email=result.get("email", ""),
        )
    else:
        return LicenseStatus(
            valid=False,
            error=result.get("error", "unknown"),
            tier="free",
        )


def clear_cache():
    """Clear the local license cache (forces re-verification)."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()


def get_checkout_url() -> str:
    """Get the Stripe checkout URL for KLAW subscription."""
    return "https://held-eta.vercel.app/api/klaw/checkout"
