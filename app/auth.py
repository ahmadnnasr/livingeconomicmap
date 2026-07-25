
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.settings import get_settings
security=HTTPBasic()

def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    s=get_settings()
    ok=secrets.compare_digest(credentials.username.encode(),s.dashboard_username.encode()) and secrets.compare_digest(credentials.password.encode(),s.dashboard_password.encode())
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials", headers={"WWW-Authenticate":"Basic"})
    return credentials.username
