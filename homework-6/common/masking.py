"""PII masking utilities.

Account numbers and customer names must never appear in plaintext logs.
"""

import re


_ACCOUNT_PATTERN = re.compile(r"ACC-\d+", re.IGNORECASE)


def mask_account(account_id: str) -> str:
    """Return a masked representation of an account identifier.

    Example: ``ACC-1001`` → ``ACC-****``
    """
    if not account_id:
        return account_id
    # Keep the prefix, replace digits with asterisks
    return _ACCOUNT_PATTERN.sub(lambda m: m.group(0).split("-")[0] + "-****", account_id)


def mask_accounts_in_dict(data: dict) -> dict:
    """Return a shallow copy of *data* with account fields masked.

    Only the top-level ``source_account`` and ``destination_account`` keys are
    masked; nested structures are left untouched (they should not be logged).
    """
    sensitive_keys = {"source_account", "destination_account"}
    return {
        k: mask_account(v) if k in sensitive_keys and isinstance(v, str) else v
        for k, v in data.items()
    }
