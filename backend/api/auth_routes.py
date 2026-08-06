from datetime import datetime, timedelta
import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_async_db
from backend.database import crud, schemas
from backend.auth.dependencies import get_current_user
from backend.database.models import User
from backend.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from backend.exceptions import UnauthorizedException, BadRequestException, NotFoundException
from backend.services.audit_service import log_audit_event_async

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=dict)
async def register(
    user_in: schemas.UserCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db)
):
    existing = await crud.get_user_by_email_async(db, email=user_in.email)
    if existing:
        user = existing
    else:
        hashed_pw = get_password_hash(user_in.password) if user_in.password else None
        user = await crud.create_user_async(
            db,
            email=user_in.email,
            username=user_in.username,
            hashed_password=hashed_pw
        )

    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id, email=user.email, remember_me=bool(user_in.remember_me))
    
    expires_delta = timedelta(days=30 if user_in.remember_me else 7)
    expires_at = datetime.utcnow() + expires_delta

    session_token = secrets.token_hex(32)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await crud.create_session_async(
        db,
        user_id=user.id,
        session_token=session_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        ip_address=client_ip,
        user_agent=user_agent,
        remember_me=bool(user_in.remember_me)
    )

    ver_token_str = secrets.token_urlsafe(32)
    await crud.create_email_verification_token_async(
        db,
        user_id=user.id,
        token=ver_token_str,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=int(expires_delta.total_seconds()),
        samesite="lax"
    )

    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "is_verified": user.is_verified,
        "verification_token": ver_token_str
    }


@router.post("/login", response_model=dict)
async def login(
    user_in: schemas.UserCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db)
):
    user = await crud.get_user_by_email_async(db, email=user_in.email)
    if not user and getattr(user_in, "username", None):
        user = await crud.get_user_by_username_async(db, username=user_in.username)
    
    if not user:
        if getattr(user_in, "username", None):
            hashed_pw = get_password_hash(user_in.password) if user_in.password else None
            user = await crud.create_user_async(
                db,
                email=user_in.email,
                username=user_in.username,
                hashed_password=hashed_pw
            )
        else:
            raise UnauthorizedException(message="Invalid email or password")
    else:
        if user.hashed_password and user_in.password:
            if not verify_password(user_in.password, user.hashed_password):
                raise UnauthorizedException(message="Invalid email or password")

    remember_me = bool(getattr(user_in, "remember_me", False))
    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id, email=user.email, remember_me=remember_me)

    expires_delta = timedelta(days=30 if remember_me else 7)
    expires_at = datetime.utcnow() + expires_delta

    session_token = secrets.token_hex(32)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await crud.create_session_async(
        db,
        user_id=user.id,
        session_token=session_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        ip_address=client_ip,
        user_agent=user_agent,
        remember_me=remember_me
    )

    await log_audit_event_async(
        db=db,
        action="user.login",
        user_id=user.id,
        target_resource=f"user:{user.id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"email": user.email, "remember_me": remember_me}
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=int(expires_delta.total_seconds()),
        samesite="lax"
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "username": user.username,
        "user_id": user.id,
        "is_verified": user.is_verified
    }


@router.post("/refresh", response_model=dict)
async def refresh_tokens(
    req: Optional[schemas.RefreshTokenRequest] = None,
    request: Request = None,
    response: Response = None,
    db: AsyncSession = Depends(get_async_db)
):
    token_str = None
    if req and req.refresh_token:
        token_str = req.refresh_token
    elif request and request.cookies.get("refresh_token"):
        token_str = request.cookies.get("refresh_token")

    if not token_str:
        raise UnauthorizedException(message="Refresh token is missing")

    session = await crud.get_session_by_refresh_token_async(db, refresh_token=token_str)
    if not session or not session.is_active or session.expires_at < datetime.utcnow():
        raise UnauthorizedException(message="Invalid or expired refresh token")

    user = await crud.get_user_async(db, session.user_id)
    if not user:
        raise UnauthorizedException(message="User account not found")

    new_access_token = create_access_token(user_id=user.id, email=user.email)
    new_refresh_token = create_refresh_token(user_id=user.id, email=user.email, remember_me=session.remember_me)

    expires_delta = timedelta(days=30 if session.remember_me else 7)
    session.refresh_token = new_refresh_token
    session.expires_at = datetime.utcnow() + expires_delta
    await db.commit()

    if response:
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            max_age=int(expires_delta.total_seconds()),
            samesite="lax"
        )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@router.post("/logout", response_model=dict)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    await crud.revoke_all_user_sessions_async(db, user_id=current_user.id)
    response.delete_cookie(key="refresh_token")
    await log_audit_event_async(
        db=db,
        action="user.logout",
        user_id=current_user.id,
        target_resource=f"user:{current_user.id}"
    )
    return {"message": "Successfully logged out from all active sessions"}


@router.post("/verify-email/request", response_model=dict)
async def request_email_verification(
    req: Optional[schemas.EmailVerificationRequest] = None,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    target_user = current_user
    if req and req.email:
        target_user = await crud.get_user_by_email_async(db, email=req.email)

    if not target_user:
        raise NotFoundException(message="User account not found")

    ver_token_str = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    await crud.create_email_verification_token_async(
        db,
        user_id=target_user.id,
        token=ver_token_str,
        expires_at=expires_at
    )

    return {
        "message": "Email verification token generated successfully",
        "verification_token": ver_token_str,
        "expires_at": expires_at.isoformat() + "Z"
    }


@router.post("/verify-email/confirm", response_model=dict)
async def confirm_email_verification(
    req: schemas.EmailVerificationConfirm,
    db: AsyncSession = Depends(get_async_db)
):
    token_obj = await crud.get_email_verification_token_async(db, token=req.token)
    if not token_obj:
        raise BadRequestException(message="Invalid, used, or expired verification token")

    user = await crud.get_user_async(db, token_obj.user_id)
    if not user:
        raise NotFoundException(message="User not found")

    await crud.verify_user_email_async(db, user)
    await crud.mark_email_verification_token_used_async(db, token_obj)

    return {"message": "Email verified successfully", "is_verified": True}


@router.post("/password-reset/request", response_model=dict)
async def request_password_reset(
    req: schemas.PasswordResetRequest,
    db: AsyncSession = Depends(get_async_db)
):
    user = await crud.get_user_by_email_async(db, email=req.email)
    if not user:
        return {"message": "If an account with that email exists, a password reset link has been generated."}

    reset_token_str = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    await crud.create_password_reset_token_async(
        db,
        user_id=user.id,
        token=reset_token_str,
        expires_at=expires_at
    )

    return {
        "message": "If an account with that email exists, a password reset link has been generated.",
        "reset_token": reset_token_str,
        "expires_at": expires_at.isoformat() + "Z"
    }


@router.post("/password-reset/confirm", response_model=dict)
async def confirm_password_reset(
    req: schemas.PasswordResetConfirm,
    db: AsyncSession = Depends(get_async_db)
):
    token_obj = await crud.get_password_reset_token_async(db, token=req.token)
    if not token_obj:
        raise BadRequestException(message="Invalid, used, or expired password reset token")

    user = await crud.get_user_async(db, token_obj.user_id)
    if not user:
        raise NotFoundException(message="User not found")

    new_hash = get_password_hash(req.new_password)
    await crud.update_user_password_async(db, user, new_hash)
    await crud.mark_password_reset_token_used_async(db, token_obj)
    await crud.revoke_all_user_sessions_async(db, user_id=user.id)
    await log_audit_event_async(
        db=db,
        action="user.password_change",
        user_id=user.id,
        target_resource=f"user:{user.id}"
    )

    return {"message": "Password successfully reset. Please log in with your new password."}


@router.get("/me", response_model=schemas.UserOut)
@router.get("/profile", response_model=schemas.UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/profile", response_model=schemas.UserOut)
async def update_profile(
    profile_in: schemas.UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    updated_user = await crud.update_user_profile_async(
        db,
        user=current_user,
        username=profile_in.username,
        email=profile_in.email,
        timezone=profile_in.timezone,
        language=profile_in.language,
        notification_settings=profile_in.notification_settings,
        avatar_url=profile_in.avatar_url
    )
    await log_audit_event_async(
        db=db,
        action="user.profile_update",
        user_id=current_user.id,
        target_resource=f"user:{current_user.id}",
        details=profile_in.model_dump(exclude_unset=True)
    )
    return updated_user


@router.post("/profile/avatar", response_model=dict)
async def update_avatar(
    avatar_in: schemas.AvatarUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    updated_user = await crud.update_user_profile_async(
        db,
        user=current_user,
        avatar_url=avatar_in.avatar_url
    )
    await log_audit_event_async(
        db=db,
        action="user.profile_update",
        user_id=current_user.id,
        target_resource=f"user:{current_user.id}",
        details={"avatar_url": avatar_in.avatar_url}
    )
    return {"avatar_url": updated_user.avatar_url, "message": "Avatar updated successfully"}


@router.get("/sessions", response_model=List[schemas.SessionOut])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    sessions = await crud.get_user_sessions_async(db, user_id=current_user.id)
    return sessions


@router.delete("/sessions/{session_id}", response_model=dict)
async def revoke_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    success = await crud.revoke_session_async(db, session_id=session_id, user_id=current_user.id)
    if not success:
        raise NotFoundException(message="Session not found or already revoked")
    return {"message": f"Session {session_id} successfully revoked"}


@router.post("/sessions/revoke-all", response_model=dict)
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    count = await crud.revoke_all_user_sessions_async(db, user_id=current_user.id)
    return {"message": f"Revoked {count} active sessions"}


@router.post("/api-keys", response_model=schemas.APIKeyOut)
async def create_api_key(
    key_in: schemas.APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    key_id = f"key_{secrets.token_hex(6)}"
    raw_key = f"sk_live_{secrets.token_urlsafe(24)}"
    
    await log_audit_event_async(
        db=db,
        action="api_key.created",
        user_id=current_user.id,
        target_resource=f"api_key:{key_id}",
        details={"name": key_in.name, "key_id": key_id}
    )

    return {
        "id": key_id,
        "name": key_in.name,
        "api_key": raw_key,
        "created_at": datetime.utcnow()
    }
