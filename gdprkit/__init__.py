"""GDPRKIT - GDPR/CCPA DSAR, RoPA, and cookie-consent compliance toolkit.

Standard-library only, zero install. Real engine for:
  - DSAR (Data Subject Access Request) deadline + status tracking
  - RoPA (Record of Processing Activities) validation under GDPR Art. 30
  - Cookie-consent banner / category auditing (ePrivacy + GDPR consent)
"""
from .core import (
    DSARRequest,
    DSARTracker,
    ROPAEntry,
    validate_ropa,
    audit_cookies,
    DSAR_LEGAL_DAYS,
    DSAR_EXTENSION_DAYS,
)

TOOL_NAME = "gdprkit"
TOOL_VERSION = "1.0.0"

__all__ = [
    "DSARRequest",
    "DSARTracker",
    "ROPAEntry",
    "validate_ropa",
    "audit_cookies",
    "DSAR_LEGAL_DAYS",
    "DSAR_EXTENSION_DAYS",
    "TOOL_NAME",
    "TOOL_VERSION",
]
