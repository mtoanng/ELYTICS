import logging
import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)  # Don't auto-error on missing credentials
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        tenant_id = os.getenv("BACKEND_AZURE_TENANT_ID")
        if not tenant_id:
            raise RuntimeError("BACKEND_AZURE_TENANT_ID is not set")
        jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=300)
    return _jwks_client


def verify_oidc_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Dirty disable auth for testing - set DISABLE_AUTH=true to skip token verification
    if os.getenv("DISABLE_AUTH", "false").lower() == "true":
        logger.warning("AUTH DISABLED - This should only be used for testing!")
        return {"oid": "test-user", "groups": ["IdM2BCD_holmes_pemely_development"]}

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        tenant_id = os.getenv("BACKEND_AZURE_TENANT_ID")
        client_id = os.getenv("BACKEND_AZURE_CLIENT_ID")
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        )
        return decoded
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidAudienceError:
        logger.warning("Token audience mismatch")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token audience mismatch",
        )
    except jwt.InvalidIssuerError:
        logger.warning("Token issuer mismatch")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token issuer mismatch",
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("Invalid token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as exc:
        logger.exception("Unexpected error during token verification")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unexpected error: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_groups(required_groups):
    def dependency(token: dict = Depends(verify_oidc_token)):
        user_groups = token.get("groups", [])
        if not any(group in user_groups for group in required_groups):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have required group membership",
            )
        return token

    return dependency
