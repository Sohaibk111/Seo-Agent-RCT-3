from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.database import get_async_db
from backend.auth.security import decode_access_token
from backend.database.crud import get_user_async, create_user_async
from backend.database.models import User
from backend.exceptions import UnauthorizedException, ForbiddenException

async def get_current_user(
    request: Request,
    authorization: str = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_async_db)
) -> User:
    if not authorization:
        raise UnauthorizedException(message="Authentication credentials were missing or invalid")
    
    payload = decode_access_token(authorization)
    if not payload:
        raise UnauthorizedException(message="Authentication credentials were missing or invalid")

    user_id = payload.get("user_id")
    email = payload.get("email")

    user = await get_user_async(db, user_id)
    if not user and email:
        user = await create_user_async(db, email=email, username=email.split("@")[0])

    if not user:
        raise UnauthorizedException(message="User account not found")

    request.state.user_id = user.id
    return user

async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Verifies that the authenticated user possesses administrative privileges."""
    role = getattr(current_user, "role", "user")
    if role not in ("admin", "superuser") and current_user.id != 1:
        raise ForbiddenException(message="Forbidden: Administrative privileges required")
    return current_user

async def require_verified_email(
    current_user: User = Depends(get_current_user)
) -> User:
    """Enforces that the current authenticated user has completed email verification."""
    if not current_user.is_verified:
        raise ForbiddenException(message="Email verification required to access this resource")
    return current_user
