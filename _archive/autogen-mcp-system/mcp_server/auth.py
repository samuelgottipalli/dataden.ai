from fastapi import HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from config.ldap_config import ldap_manager
from loguru import logger
import jwt
from datetime import datetime, timedelta
from config.settings import settings

security = HTTPBasic()


async def verify_credentials(
    credentials: HTTPBasicCredentials = Depends(security),
) -> dict:
    """
    Verify user credentials via LDAP
    Used as a dependency for protected endpoints
    """
    success, user_info = ldap_manager.authenticate_user(
        credentials.username, credentials.password
    )

    if not success:
        logger.warning(f"Failed login attempt for user: {credentials.username}")
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    logger.info(f"Successful login for user: {credentials.username}")
    return user_info or {"username": credentials.username}
