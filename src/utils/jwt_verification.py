"""
Contains functions required for jwt signature verification.
"""

import os
from typing import Any

from fastapi.security import HTTPBearer
from fastapi import Depends, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials

import jwt
from jwt import PyJWK, PyJWKClient

from starlette import status

JWKS_BACKEND_ENDPOINT: str = os.environ["JWKS_BACKEND_ENDPOINT"]
JWT_BACKEND_ISSUER: str = os.environ["JWT_BACKEND_ISSUER"]

jwks_client = PyJWKClient(JWKS_BACKEND_ENDPOINT)

security_bearer: HTTPBearer = HTTPBearer()


def verify_jwt_signature(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
) -> dict[str, Any]:
    """This function verifies JWT signature using JWKs from a JWKs endpoint on the divum-backend."""

    token = credentials.credentials

    try:
        signing_key: PyJWK = jwks_client.get_signing_key_from_jwt(token)

        payload: dict[str, Any] = jwt.decode(
            token, key=signing_key.key, algorithms=["EdDSA"], issuer=JWT_BACKEND_ISSUER
        )

        return payload

    except jwt.exceptions.PyJWKClientConnectionError as ex:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication server is unreachable.",
        ) from ex
    except jwt.exceptions.PyJWKClientError as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signing key not found. Token is invalid or outdated.",
        ) from ex
    except jwt.ExpiredSignatureError as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired."
        ) from ex
    except jwt.InvalidTokenError as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized token."
        ) from ex
