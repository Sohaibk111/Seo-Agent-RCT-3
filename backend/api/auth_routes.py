import asyncio
from datetime import datetime, timedelta
import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_async_db
from backend.database import crud, schemas
from backend.auth.dependencies import get_current_user, require_verified_email
from backend.database.models import User
from backend.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_password_hash,
    verify_password,
    validate_password_strength,
    calculate_progressive_delay,
    parse_device_info,
    LOCKOUT_THRESHOLD,
    LOCKOUT_DURATION_MINUTES,
    MAX_PASSWORD_HISTORY,
    IDLE_SESSION_TIMEOUT_HOURS
)
from backend.exceptions import UnauthorizedException, BadRequestException, NotFoundException, ForbiddenException
from backend.services.audit_service import log_audit_event_async

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=dict)
async def register(
    user_in: schemas.UserCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db)
):
    # 1. Password strength validation
    if user_in.password:
        is_valid, errs = validate_password_strength(user_in.password)
        if not is_valid:
            raise BadRequestException(message="; ".join(errs))

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    device_data = parse_device_info(user_agent)

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
        if hashed_pw:
            await crud.add_password_history_async(db, user_id=user.id, hashed_password=hashed_pw)

    # Issue access and refresh tokens
    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id, email=user.email, remember_me=bool(user_in.remember_me))
    
    expires_delta = timedelta(days=30 if user_in.remember_me else 7)
    expires_at = datetime.utcnow() + expires_delta

    session_token = secrets.token_hex(32)
    session = await crud.create_session_async(
        db,
        user_id=user.id,
        session_token=session_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        ip_address=client_ip,
        user_agent=user_agent,
        device_name=device_data["device_name"],
        device_type=device_data["device_type"],
        remember_me=bool(user_in.remember_me)
    )

    ver_token_str = secrets.token_urlsafe(32)
    await crud.create_email_verification_token_async(
        db,
        user_id=user.id,
        token=ver_token_str,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )

    # Security event logging
    await crud.create_security_event_async(
        db=db,
        user_id=user.id,
        event_type="auth.register.success",
        status="success",
        ip_address=client_ip,
        user_agent=user_agent,
        device_info=device_data["device_name"],
        details={"email": user.email}
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
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    device_data = parse_device_info(user_agent)

    user = await crud.get_user_by_email_async(db, email=user_in.email)
    if not user and getattr(user_in, "username", None):
        user = await crud.get_user_by_username_async(db, username=user_in.username)
    
    if not user:
        if getattr(user_in, "username", None):
            # Development auto-registration fallback if username provided
            hashed_pw = get_password_hash(user_in.password) if user_in.password else None
            user = await crud.create_user_async(
                db,
                email=user_in.email,
                username=user_in.username,
                hashed_password=hashed_pw
            )
            if hashed_pw:
                await crud.add_password_history_async(db, user_id=user.id, hashed_password=hashed_pw)
        else:
            await crud.create_security_event_async(
                db=db,
                user_id=None,
                event_type="auth.login.failed",
                status="failure",
                ip_address=client_ip,
                user_agent=user_agent,
                device_info=device_data["device_name"],
                details={"email": user_in.email, "reason": "User not found"}
            )
            raise UnauthorizedException(message="Invalid email or password")

    # 1. Account Lockout Check
    is_locked, remaining_seconds = crud.is_account_locked(user)
    if is_locked:
        await crud.create_security_event_async(
            db=db,
            user_id=user.id,
            event_type="auth.login.blocked_locked",
            status="warning",
            ip_address=client_ip,
            user_agent=user_agent,
            device_info=device_data["device_name"],
            details={"remaining_seconds": remaining_seconds}
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account is temporarily locked due to excessive failed attempts. Please try again in {remaining_seconds} seconds."
        )

    # 2. Progressive Login Delay
    delay = calculate_progressive_delay(user.failed_login_attempts or 0)
    if delay > 0:
        await asyncio.sleep(delay)

    # 3. Password Verification
    if user.hashed_password and user_in.password:
        if not verify_password(user_in.password, user.hashed_password):
            # Record failed login attempt
            locked, remaining_attempts, lockout_sec = await crud.record_login_failure_async(
                db, user, ip_address=client_ip, user_agent=user_agent
            )

            await crud.create_security_event_async(
                db=db,
                user_id=user.id,
                event_type="auth.login.failed",
                status="warning" if not locked else "critical",
                ip_address=client_ip,
                user_agent=user_agent,
                device_info=device_data["device_name"],
                details={
                    "failed_attempts": user.failed_login_attempts,
                    "locked": locked,
                    "remaining_attempts": remaining_attempts
                }
            )

            if locked:
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"Account is now locked for {LOCKOUT_DURATION_MINUTES} minutes due to multiple failed login attempts."
                )

            raise UnauthorizedException(
                message=f"Invalid email or password. {remaining_attempts} attempts remaining before lockout."
            )

    # 4. Successful Authentication: Reset lockout counters & update last login
    await crud.record_login_success_async(db, user, ip_address=client_ip)

    remember_me = bool(getattr(user_in, "remember_me", False))
    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id, email=user.email, remember_me=remember_me)

    expires_delta = timedelta(days=30 if remember_me else 7)
    expires_at = datetime.utcnow() + expires_delta

    session_token = secrets.token_hex(32)
    session = await crud.create_session_async(
        db,
        user_id=user.id,
        session_token=session_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        ip_address=client_ip,
        user_agent=user_agent,
        device_name=device_data["device_name"],
        device_type=device_data["device_type"],
        remember_me=remember_me
    )

    await crud.create_security_event_async(
        db=db,
        user_id=user.id,
        event_type="auth.login.success",
        status="success",
        ip_address=client_ip,
        user_agent=user_agent,
        device_info=device_data["device_name"],
        details={"session_id": session.id, "remember_me": remember_me}
    )

    await log_audit_event_async(
        db=db,
        action="user.login",
        user_id=user.id,
        target_resource=f"user:{user.id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"email": user.email, "remember_me": remember_me, "device": device_data["device_name"]}
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
        "is_verified": user.is_verified,
        "last_login_at": user.last_login_at.isoformat() + "Z" if user.last_login_at else None,
        "last_login_ip": user.last_login_ip
    }


@router.post("/refresh", response_model=dict)
async def refresh_tokens(
    req: Optional[schemas.RefreshTokenRequest] = None,
    request: Request = None,
    response: Response = None,
    db: AsyncSession = Depends(get_async_db)
):
    client_ip = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None
    device_data = parse_device_info(user_agent)

    token_str = None
    if req and req.refresh_token:
        token_str = req.refresh_token
    elif request and request.cookies.get("refresh_token"):
        token_str = request.cookies.get("refresh_token")

    if not token_str:
        raise UnauthorizedException(message="Refresh token is missing")

    # 1. REFRESH TOKEN REUSE DETECTION (Breach Detection)
    is_reused, compromised_user_id = await crud.is_refresh_token_reused_async(db, token_str)
    if is_reused and compromised_user_id:
        # Compromise detected! Immediately revoke ALL sessions for this user
        revoked_count = await crud.revoke_all_user_sessions_async(db, user_id=compromised_user_id)
        await crud.create_security_event_async(
            db=db,
            user_id=compromised_user_id,
            event_type="auth.refresh_token_reuse_detected",
            status="critical",
            ip_address=client_ip,
            user_agent=user_agent,
            device_info=device_data["device_name"],
            details={
                "action": "mass_session_revocation",
                "revoked_sessions_count": revoked_count,
                "warning": "Attempted replay of invalidated refresh token"
            }
        )
        if response:
            response.delete_cookie("refresh_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Suspicious token activity detected. All active sessions have been revoked for your security."
        )

    # 2. Look up active session
    session = await crud.get_session_by_refresh_token_async(db, refresh_token=token_str)
    if not session or not session.is_active:
        raise UnauthorizedException(message="Invalid or revoked refresh token")

    # 3. Check absolute and idle session expiration
    now = datetime.utcnow()
    if session.expires_at < now:
        session.is_active = False
        await db.commit()
        raise UnauthorizedException(message="Refresh token has expired. Please log in again.")

    if session.last_active_at and (now - session.last_active_at) > timedelta(hours=IDLE_SESSION_TIMEOUT_HOURS):
        session.is_active = False
        await db.commit()
        raise UnauthorizedException(message="Session expired due to inactivity. Please log in again.")

    user = await crud.get_user_async(db, session.user_id)
    if not user:
        raise UnauthorizedException(message="User account not found")

    # 4. REFRESH TOKEN ROTATION: Register old token into used tokens registry
    await crud.register_used_refresh_token_async(
        db,
        user_id=user.id,
        refresh_token_str=token_str,
        session_id=session.id
    )

    # 5. Issue new tokens
    new_access_token = create_access_token(user_id=user.id, email=user.email)
    new_refresh_token = create_refresh_token(user_id=user.id, email=user.email, remember_me=session.remember_me)

    expires_delta = timedelta(days=30 if session.remember_me else 7)
    session.refresh_token = new_refresh_token
    session.expires_at = datetime.utcnow() + expires_delta
    session.last_active_at = datetime.utcnow()
    if client_ip:
        session.last_ip = client_ip
    await db.commit()

    await crud.create_security_event_async(
        db=db,
        user_id=user.id,
        event_type="auth.token_refreshed",
        status="success",
        ip_address=client_ip,
        user_agent=user_agent,
        device_info=device_data["device_name"],
        details={"session_id": session.id}
    )

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
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Invalidate sessions
    await crud.revoke_all_user_sessions_async(db, user_id=current_user.id)
    response.delete_cookie(key="refresh_token")

    await crud.create_security_event_async(
        db=db,
        user_id=current_user.id,
        event_type="auth.logout",
        status="success",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"all_sessions_revoked": True}
    )

    await log_audit_event_async(
        db=db,
        action="user.logout",
        user_id=current_user.id,
        target_resource=f"user:{current_user.id}"
    )
    return {"message": "Successfully logged out from all active sessions"}


@router.post("/change-password", response_model=dict)
async def change_password(
    req: schemas.PasswordChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # 1. Verify current password
    if current_user.hashed_password and not verify_password(req.current_password, current_user.hashed_password):
        await crud.create_security_event_async(
            db=db,
            user_id=current_user.id,
            event_type="auth.password_change.failed",
            status="warning",
            ip_address=client_ip,
            user_agent=user_agent,
            details={"reason": "Incorrect current password"}
        )
        raise UnauthorizedException(message="Current password does not match")

    # 2. Validate new password strength
    is_valid, errs = validate_password_strength(req.new_password)
    if not is_valid:
        raise BadRequestException(message="; ".join(errs))

    # 3. Password History Check (Prevent reusing last 5 passwords)
    is_in_history = await crud.check_password_history_async(
        db, user_id=current_user.id, plain_password=req.new_password, max_history=MAX_PASSWORD_HISTORY
    )
    if is_in_history or (current_user.hashed_password and verify_password(req.new_password, current_user.hashed_password)):
        raise BadRequestException(message=f"Cannot reuse any of your last {MAX_PASSWORD_HISTORY} passwords. Please choose a new password.")

    # 4. Hash and save new password
    new_hash = get_password_hash(req.new_password)
    await crud.update_user_password_async(db, current_user, new_hash)
    await crud.add_password_history_async(db, user_id=current_user.id, hashed_password=new_hash)

    # 5. Revoke existing sessions
    await crud.revoke_all_user_sessions_async(db, user_id=current_user.id)

    await crud.create_security_event_async(
        db=db,
        user_id=current_user.id,
        event_type="auth.password_change.success",
        status="success",
        ip_address=client_ip,
        user_agent=user_agent
    )

    await log_audit_event_async(
        db=db,
        action="user.password_change",
        user_id=current_user.id,
        target_resource=f"user:{current_user.id}"
    )

    return {"message": "Password changed successfully. Please log in again."}


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

    await crud.create_security_event_async(
        db=db,
        user_id=user.id,
        event_type="auth.email_verified",
        status="success",
        details={"email": user.email}
    )

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
    # 1. Password complexity check
    is_valid, errs = validate_password_strength(req.new_password)
    if not is_valid:
        raise BadRequestException(message="; ".join(errs))

    token_obj = await crud.get_password_reset_token_async(db, token=req.token)
    if not token_obj:
        raise BadRequestException(message="Invalid, used, or expired password reset token")

    user = await crud.get_user_async(db, token_obj.user_id)
    if not user:
        raise NotFoundException(message="User not found")

    # 2. Password history check
    is_in_history = await crud.check_password_history_async(
        db, user_id=user.id, plain_password=req.new_password, max_history=MAX_PASSWORD_HISTORY
    )
    if is_in_history or (user.hashed_password and verify_password(req.new_password, user.hashed_password)):
        raise BadRequestException(message=f"Cannot reuse any of your last {MAX_PASSWORD_HISTORY} passwords. Please choose a new password.")

    new_hash = get_password_hash(req.new_password)
    await crud.update_user_password_async(db, user, new_hash)
    await crud.add_password_history_async(db, user_id=user.id, hashed_password=new_hash)
    await crud.mark_password_reset_token_used_async(db, token_obj)
    await crud.revoke_all_user_sessions_async(db, user_id=user.id)

    await crud.create_security_event_async(
        db=db,
        user_id=user.id,
        event_type="auth.password_reset.success",
        status="success"
    )

    await log_audit_event_async(
        db=db,
        action="user.password_change",
        user_id=user.id,
        target_resource=f"user:{user.id}"
    )

    return {"message": "Password successfully reset. Please log in with your new password."}


@router.get("/csrf-token", response_model=schemas.CSRFTokenOut)
async def get_csrf_token(request: Request):
    """Issues a cryptographically secure CSRF token for state-changing requests."""
    csrf_token = secrets.token_hex(32)
    return schemas.CSRFTokenOut(csrf_token=csrf_token)


@router.get("/security-events", response_model=List[schemas.SecurityEventOut])
async def list_security_events(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieves authenticated user's security events and login audit trail."""
    events = await crud.get_security_events_async(db, user_id=current_user.id, limit=limit, offset=offset)
    return events


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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    sessions = await crud.get_user_sessions_async(db, user_id=current_user.id)
    client_ip = request.client.host if request.client else None
    
    # Enrich session models with current flag
    results = []
    for s in sessions:
        out = schemas.SessionOut.from_orm(s) if hasattr(schemas.SessionOut, "from_orm") else schemas.SessionOut.model_validate(s)
        if client_ip and s.ip_address == client_ip:
            out.is_current = True
        results.append(out)
    return results


@router.delete("/sessions/{session_id}", response_model=dict)
async def revoke_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    success = await crud.revoke_session_async(db, session_id=session_id, user_id=current_user.id)
    if not success:
        raise NotFoundException(message="Session not found or already revoked")
    
    await crud.create_security_event_async(
        db=db,
        user_id=current_user.id,
        event_type="auth.session_revoked",
        status="info",
        details={"session_id": session_id}
    )
    return {"message": f"Session {session_id} successfully revoked"}


@router.post("/sessions/revoke-all", response_model=dict)
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    count = await crud.revoke_all_user_sessions_async(db, user_id=current_user.id)
    await crud.create_security_event_async(
        db=db,
        user_id=current_user.id,
        event_type="auth.sessions_revoked_all",
        status="warning",
        details={"revoked_count": count}
    )
    return {"message": f"Revoked {count} active sessions"}


@router.post("/api-keys", response_model=schemas.APIKeyOut)
async def create_api_key(
    key_in: schemas.APIKeyCreate,
    current_user: User = Depends(require_verified_email),
    db: AsyncSession = Depends(get_async_db)
):
    """Creates an API key. Strictly enforces email verification requirement."""
    key_id = f"key_{secrets.token_hex(6)}"
    raw_key = f"sk_live_{secrets.token_urlsafe(24)}"
    
    await log_audit_event_async(
        db=db,
        action="api_key.created",
        user_id=current_user.id,
        target_resource=f"api_key:{key_id}",
        details={"name": key_in.name, "key_id": key_id}
    )

    await crud.create_security_event_async(
        db=db,
        user_id=current_user.id,
        event_type="auth.api_key_created",
        status="info",
        details={"key_id": key_id, "name": key_in.name}
    )

    return {
        "id": key_id,
        "name": key_in.name,
        "api_key": raw_key,
        "created_at": datetime.utcnow()
    }
