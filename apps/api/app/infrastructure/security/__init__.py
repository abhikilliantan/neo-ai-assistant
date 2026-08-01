"""Security primitives: password hashing, JWT, API keys, email normalization."""

from app.infrastructure.security.api_keys import (
    DEFAULT_SCOPES,
    KEY_PREFIX,
    SUPPORTED_SCOPES,
    GeneratedApiKey,
    generate_api_key,
    hash_api_key,
    prefix_of,
    verify_api_key,
)
from app.infrastructure.security.emails import normalize_email
from app.infrastructure.security.passwords import hash_password, verify_password
from app.infrastructure.security.tokens import (
    ExpiredTokenError,
    InvalidTokenError,
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    decode_token,
    hash_refresh_token,
)

__all__ = [
    "DEFAULT_SCOPES",
    "KEY_PREFIX",
    "SUPPORTED_SCOPES",
    "ExpiredTokenError",
    "GeneratedApiKey",
    "InvalidTokenError",
    "TokenPayload",
    "create_access_token",
    "create_refresh_token",
    "decode_access_token",
    "decode_refresh_token",
    "decode_token",
    "generate_api_key",
    "hash_api_key",
    "hash_password",
    "hash_refresh_token",
    "normalize_email",
    "prefix_of",
    "verify_api_key",
    "verify_password",
]
