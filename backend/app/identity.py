"""Local pilot identities. Each seeded resident stands for one participating household."""
import hmac
import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)
DEMO_RESIDENTS = {"resident-1", "resident-2", "resident-3"}


def resident(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials and credentials.credentials in DEMO_RESIDENTS:
        return credentials.credentials
    raise HTTPException(401, "Select a pilot resident")


def reviewer(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    secret = os.environ.get("REVIEWER_TOKEN", "")
    if secret and credentials and hmac.compare_digest(secret.encode(), credentials.credentials.encode()):
        return "reviewer-1"
    raise HTTPException(403, "Reviewer access required")
