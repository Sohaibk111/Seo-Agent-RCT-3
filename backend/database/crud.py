import re
from datetime import datetime, timedelta
from typing import List, Optional, Union, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, update, insert, func, and_

from backend.database.models import (
    User, Website, AuditResult, Lead, Report, KeywordResult, RankCheck, Job,
    UserSession, PasswordResetToken, EmailVerificationToken, Organization,
    Membership, Invitation, OrganizationAuditEvent, PasswordHistory, UsedRefreshToken, SecurityEvent, Project, AuditLog
)
from backend.exceptions import ConflictException
from backend.services.audit_service import log_audit_event_async
from backend.database.pagination import (
    paginate,
    async_paginate,
    cursor_paginate,
    async_cursor_paginate,
    encode_cursor,
    decode_cursor
)

# --- USER CRUD ---
def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

async def get_user_async(db: AsyncSession, user_id: int) -> Optional[User]:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

async def get_user_by_email_async(db: AsyncSession, email: str) -> Optional[User]:
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    return result.scalars().first()

def create_user(db: Session, email: str, username: str, hashed_password: Optional[str] = None) -> User:
    db_user = User(email=email, username=username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

async def create_user_async(db: AsyncSession, email: str, username: str, hashed_password: Optional[str] = None, is_verified: bool = False, timezone: str = "UTC", language: str = "en") -> User:
    db_user = User(
        email=email,
        username=username,
        hashed_password=hashed_password,
        is_verified=is_verified,
        timezone=timezone,
        language=language
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_user_by_username_async(db: AsyncSession, username: str) -> Optional[User]:
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalars().first()

async def update_user_profile_async(
    db: AsyncSession,
    user: User,
    username: Optional[str] = None,
    email: Optional[str] = None,
    timezone: Optional[str] = None,
    language: Optional[str] = None,
    notification_settings: Optional[dict] = None,
    avatar_url: Optional[str] = None
) -> User:
    if username is not None:
        user.username = username
    if email is not None:
        user.email = email
    if timezone is not None:
        user.timezone = timezone
    if language is not None:
        user.language = language
    if notification_settings is not None:
        user.notification_settings = notification_settings
    if avatar_url is not None:
        user.avatar_url = avatar_url

    await db.commit()
    await db.refresh(user)
    return user

async def update_user_password_async(db: AsyncSession, user: User, hashed_password: str) -> User:
    user.hashed_password = hashed_password
    await db.commit()
    await db.refresh(user)
    return user

async def verify_user_email_async(db: AsyncSession, user: User) -> User:
    user.is_verified = True
    await db.commit()
    await db.refresh(user)
    return user

def is_account_locked(user: User) -> Tuple[bool, int]:
    """Checks if the user account is locked due to excessive failed login attempts."""
    if not user.locked_until:
        return False, 0
    now = datetime.utcnow()
    if user.locked_until > now:
        remaining_seconds = int((user.locked_until - now).total_seconds())
        return True, max(1, remaining_seconds)
    return False, 0

async def record_login_failure_async(
    db: AsyncSession,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Tuple[bool, int, int]:
    """
    Increments failed login attempts and sets lockout if threshold is exceeded.
    Returns: (is_locked, remaining_attempts, lockout_seconds)
    """
    from backend.auth.security import LOCKOUT_THRESHOLD, LOCKOUT_DURATION_MINUTES
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    locked = False
    lockout_seconds = 0

    if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
        user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        locked = True
        lockout_seconds = LOCKOUT_DURATION_MINUTES * 60

    await db.commit()
    await db.refresh(user)

    remaining_attempts = max(0, LOCKOUT_THRESHOLD - user.failed_login_attempts)
    return locked, remaining_attempts, lockout_seconds

async def record_login_success_async(
    db: AsyncSession,
    user: User,
    ip_address: Optional[str] = None
) -> None:
    """Resets failed login attempts and updates last login metadata."""
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    if ip_address:
        user.last_login_ip = ip_address
    await db.commit()
    await db.refresh(user)


# --- PASSWORD HISTORY CRUD ---
async def add_password_history_async(db: AsyncSession, user_id: int, hashed_password: str) -> PasswordHistory:
    history = PasswordHistory(
        user_id=user_id,
        hashed_password=hashed_password,
        created_at=datetime.utcnow()
    )
    db.add(history)
    await db.commit()
    await db.refresh(history)
    return history

async def check_password_history_async(db: AsyncSession, user_id: int, plain_password: str, max_history: int = 5) -> bool:
    """
    Returns True if the proposed plain password matches ANY of the user's last N recorded passwords.
    """
    from backend.auth.security import verify_password
    stmt = select(PasswordHistory).where(
        PasswordHistory.user_id == user_id
    ).order_by(PasswordHistory.created_at.desc()).limit(max_history)
    result = await db.execute(stmt)
    histories = result.scalars().all()
    for h in histories:
        if verify_password(plain_password, h.hashed_password):
            return True
    return False


# --- REFRESH TOKEN ROTATION & REUSE TRACKING ---
async def register_used_refresh_token_async(
    db: AsyncSession,
    user_id: int,
    refresh_token_str: str,
    session_id: Optional[int] = None
) -> UsedRefreshToken:
    from backend.auth.security import hash_token
    token_hash = hash_token(refresh_token_str)
    used_token = UsedRefreshToken(
        user_id=user_id,
        session_id=session_id,
        token_hash=token_hash,
        revoked_at=datetime.utcnow(),
        created_at=datetime.utcnow()
    )
    db.add(used_token)
    await db.commit()
    return used_token

async def is_refresh_token_reused_async(db: AsyncSession, refresh_token_str: str) -> Tuple[bool, Optional[int]]:
    """
    Checks if a refresh token was previously used/rotated.
    Returns: (is_reused, user_id)
    """
    from backend.auth.security import hash_token
    token_hash = hash_token(refresh_token_str)
    stmt = select(UsedRefreshToken).where(UsedRefreshToken.token_hash == token_hash)
    result = await db.execute(stmt)
    entry = result.scalars().first()
    if entry:
        return True, entry.user_id
    return False, None


# --- SECURITY EVENTS AUDIT CRUD ---
async def create_security_event_async(
    db: AsyncSession,
    event_type: str,
    user_id: Optional[int] = None,
    status: str = "info",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    device_info: Optional[str] = None,
    details: Optional[dict] = None
) -> SecurityEvent:
    event = SecurityEvent(
        user_id=user_id,
        event_type=event_type,
        status=status,
        ip_address=ip_address,
        user_agent=user_agent,
        device_info=device_info,
        details=details or {},
        created_at=datetime.utcnow()
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event

async def get_security_events_async(
    db: AsyncSession,
    user_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
) -> List[SecurityEvent]:
    stmt = select(SecurityEvent)
    if user_id is not None:
        stmt = stmt.where(SecurityEvent.user_id == user_id)
    stmt = stmt.order_by(SecurityEvent.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --- SESSION CRUD ---
async def create_session_async(
    db: AsyncSession,
    user_id: int,
    session_token: str,
    refresh_token: str,
    expires_at: datetime,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    device_name: Optional[str] = None,
    device_type: Optional[str] = None,
    remember_me: bool = False
) -> UserSession:
    session = UserSession(
        user_id=user_id,
        session_token=session_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        ip_address=ip_address,
        last_ip=ip_address,
        user_agent=user_agent,
        device_name=device_name,
        device_type=device_type,
        remember_me=remember_me,
        last_active_at=datetime.utcnow(),
        is_active=True
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

async def touch_session_activity_async(db: AsyncSession, session: UserSession, ip_address: Optional[str] = None) -> None:
    session.last_active_at = datetime.utcnow()
    if ip_address:
        session.last_ip = ip_address
    await db.commit()

async def get_session_by_refresh_token_async(db: AsyncSession, refresh_token: str) -> Optional[UserSession]:
    stmt = select(UserSession).where(
        UserSession.refresh_token == refresh_token,
        UserSession.is_active == True
    )
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_session_by_token_async(db: AsyncSession, session_token: str) -> Optional[UserSession]:
    stmt = select(UserSession).where(
        UserSession.session_token == session_token,
        UserSession.is_active == True
    )
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_user_sessions_async(db: AsyncSession, user_id: int) -> List[UserSession]:
    stmt = select(UserSession).where(
        UserSession.user_id == user_id,
        UserSession.is_active == True
    ).order_by(UserSession.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def revoke_session_async(db: AsyncSession, session_id: int, user_id: int) -> bool:
    stmt = select(UserSession).where(
        UserSession.id == session_id,
        UserSession.user_id == user_id
    )
    result = await db.execute(stmt)
    session = result.scalars().first()
    if session:
        session.is_active = False
        await db.commit()
        return True
    return False

async def revoke_all_user_sessions_async(db: AsyncSession, user_id: int, except_session_id: Optional[int] = None) -> int:
    stmt = update(UserSession).where(
        UserSession.user_id == user_id,
        UserSession.is_active == True
    )
    if except_session_id is not None:
        stmt = stmt.where(UserSession.id != except_session_id)
    stmt = stmt.values(is_active=False, updated_at=datetime.utcnow())
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


# --- PASSWORD RESET TOKEN CRUD ---
async def create_password_reset_token_async(
    db: AsyncSession,
    user_id: int,
    token: str,
    expires_at: datetime
) -> PasswordResetToken:
    reset_token = PasswordResetToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        is_used=False
    )
    db.add(reset_token)
    await db.commit()
    await db.refresh(reset_token)
    return reset_token

async def get_password_reset_token_async(db: AsyncSession, token: str) -> Optional[PasswordResetToken]:
    stmt = select(PasswordResetToken).where(
        PasswordResetToken.token == token,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > datetime.utcnow()
    )
    result = await db.execute(stmt)
    return result.scalars().first()

async def mark_password_reset_token_used_async(db: AsyncSession, token_obj: PasswordResetToken) -> None:
    token_obj.is_used = True
    await db.commit()


# --- EMAIL VERIFICATION TOKEN CRUD ---
async def create_email_verification_token_async(
    db: AsyncSession,
    user_id: int,
    token: str,
    expires_at: datetime
) -> EmailVerificationToken:
    ver_token = EmailVerificationToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        is_used=False
    )
    db.add(ver_token)
    await db.commit()
    await db.refresh(ver_token)
    return ver_token

async def get_email_verification_token_async(db: AsyncSession, token: str) -> Optional[EmailVerificationToken]:
    stmt = select(EmailVerificationToken).where(
        EmailVerificationToken.token == token,
        EmailVerificationToken.is_used == False,
        EmailVerificationToken.expires_at > datetime.utcnow()
    )
    result = await db.execute(stmt)
    return result.scalars().first()

async def mark_email_verification_token_used_async(db: AsyncSession, token_obj: EmailVerificationToken) -> None:
    token_obj.is_used = True
    await db.commit()


# --- ORGANIZATION & TEAMS CRUD ---

ROLE_HIERARCHY = {
    "Owner": 5,
    "Admin": 4,
    "Manager": 3,
    "Member": 2,
    "Viewer": 1
}

def check_role_permission(user_role: str, required_role: str) -> bool:
    user_rank = ROLE_HIERARCHY.get(user_role, 0)
    required_rank = ROLE_HIERARCHY.get(required_role, 99)
    return user_rank >= required_rank


async def create_org_audit_event_async(
    db: AsyncSession,
    org_id: int,
    action: str,
    actor_id: Optional[int] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None
) -> OrganizationAuditEvent:
    audit_event = OrganizationAuditEvent(
        organization_id=org_id,
        actor_id=actor_id,
        action=action,
        details=details or {},
        ip_address=ip_address
    )
    db.add(audit_event)
    await db.commit()
    await db.refresh(audit_event)
    return audit_event


async def get_org_audit_events_async(
    db: AsyncSession,
    org_id: int,
    limit: int = 50
) -> List[OrganizationAuditEvent]:
    stmt = (
        select(OrganizationAuditEvent)
        .options(joinedload(OrganizationAuditEvent.actor))
        .where(OrganizationAuditEvent.organization_id == org_id)
        .order_by(OrganizationAuditEvent.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_organization_async(
    db: AsyncSession,
    name: str,
    slug: str,
    creator_user_id: int,
    logo_url: Optional[str] = None,
    primary_color: Optional[str] = None,
    settings: Optional[dict] = None
) -> Organization:
    org = Organization(
        name=name,
        slug=slug,
        logo_url=logo_url,
        primary_color=primary_color,
        settings=settings or {}
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)

    # Automatically add creator as Owner
    owner_membership = Membership(
        organization_id=org.id,
        user_id=creator_user_id,
        role="Owner"
    )
    db.add(owner_membership)
    await db.commit()

    # Log audit event
    await create_org_audit_event_async(
        db,
        org_id=org.id,
        action="organization.created",
        actor_id=creator_user_id,
        details={"name": name, "slug": slug}
    )

    return org


async def get_organization_async(db: AsyncSession, org_id: int) -> Optional[Organization]:
    stmt = select(Organization).where(Organization.id == org_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_organization_by_slug_async(db: AsyncSession, slug: str) -> Optional[Organization]:
    stmt = select(Organization).where(Organization.slug == slug)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_user_organizations_async(db: AsyncSession, user_id: int) -> List[Organization]:
    stmt = (
        select(Organization)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user_id)
        .order_by(Organization.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_organization_async(
    db: AsyncSession,
    org: Organization,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    logo_url: Optional[str] = None,
    primary_color: Optional[str] = None,
    settings: Optional[dict] = None,
    actor_id: Optional[int] = None
) -> Organization:
    changes = {}
    if name is not None:
        changes["name"] = {"old": org.name, "new": name}
        org.name = name
    if slug is not None:
        changes["slug"] = {"old": org.slug, "new": slug}
        org.slug = slug
    if logo_url is not None:
        changes["logo_url"] = logo_url
        org.logo_url = logo_url
    if primary_color is not None:
        changes["primary_color"] = primary_color
        org.primary_color = primary_color
    if settings is not None:
        changes["settings"] = settings
        org.settings = settings

    org.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(org)

    await create_org_audit_event_async(
        db,
        org_id=org.id,
        action="organization.updated",
        actor_id=actor_id,
        details=changes
    )

    return org


async def delete_organization_async(db: AsyncSession, org: Organization, actor_id: Optional[int] = None) -> None:
    await create_org_audit_event_async(
        db,
        org_id=org.id,
        action="organization.deleted",
        actor_id=actor_id,
        details={"name": org.name, "slug": org.slug}
    )
    await db.delete(org)
    await db.commit()


# --- PROJECT CRUD ---

def slugify_text(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s)
    s = re.sub(r'^-+|-+$', '', s)
    return s or "project"


async def get_project_async(db: AsyncSession, project_id: int) -> Optional[Project]:
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_project_by_slug_async(db: AsyncSession, organization_id: int, slug: str) -> Optional[Project]:
    stmt = select(Project).where(
        Project.organization_id == organization_id,
        Project.slug == slug
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_project_by_id_or_slug_async(db: AsyncSession, organization_id: int, identifier: Union[int, str]) -> Optional[Project]:
    if isinstance(identifier, int) or (isinstance(identifier, str) and str(identifier).isdigit()):
        p_id = int(identifier)
        stmt = select(Project).where(
            Project.organization_id == organization_id,
            Project.id == p_id
        )
        result = await db.execute(stmt)
        project = result.scalars().first()
        if project:
            return project
    stmt = select(Project).where(
        Project.organization_id == organization_id,
        Project.slug == str(identifier)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_project_async(
    db: AsyncSession,
    organization_id: int,
    owner_id: int,
    name: str,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    status: str = "active",
    color: Optional[str] = None,
    icon: Optional[str] = None,
    timezone: str = "UTC",
    language: str = "en",
    settings: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Project:
    clean_name = name.strip()
    if not slug:
        final_slug = slugify_text(clean_name)
    else:
        final_slug = slugify_text(slug)

    existing = await get_project_by_slug_async(db, organization_id, final_slug)
    if existing:
        raise ConflictException(f"Project with slug '{final_slug}' already exists in this organization")

    project = Project(
        organization_id=organization_id,
        owner_id=owner_id,
        name=clean_name,
        slug=final_slug,
        description=description.strip() if description else None,
        status=status,
        color=color,
        icon=icon,
        timezone=timezone,
        language=language,
        settings=settings or {},
        archived=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    await log_audit_event_async(
        db,
        action="project.created",
        user_id=owner_id,
        organization_id=organization_id,
        target_resource=f"project:{project.id}",
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "project_id": project.id,
            "name": project.name,
            "slug": project.slug,
            "status": project.status
        }
    )
    await create_org_audit_event_async(
        db,
        org_id=organization_id,
        action="project.created",
        actor_id=owner_id,
        details={"project_id": project.id, "name": project.name, "slug": project.slug}
    )

    return project


async def get_org_projects_async(
    db: AsyncSession,
    organization_id: int,
    search: Optional[str] = None,
    status: Optional[str] = None,
    archived: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50
) -> Tuple[List[Project], int]:
    stmt = select(Project).where(Project.organization_id == organization_id)

    if search:
        s = f"%{search.strip()}%"
        stmt = stmt.where(or_(Project.name.ilike(s), Project.slug.ilike(s), Project.description.ilike(s)))

    if status:
        stmt = stmt.where(Project.status == status)

    if archived is not None:
        stmt = stmt.where(Project.archived == archived)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_res = await db.execute(count_stmt)
    total = count_res.scalar_one()

    stmt = stmt.order_by(Project.created_at.desc()).offset(skip).limit(limit)
    res = await db.execute(stmt)
    projects = list(res.scalars().all())

    return projects, total


async def update_project_async(
    db: AsyncSession,
    project: Project,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None,
    timezone: Optional[str] = None,
    language: Optional[str] = None,
    settings: Optional[dict] = None,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Project:
    changes = {}
    is_settings_only = (
        settings is not None and
        name is None and slug is None and description is None and
        status is None and color is None and icon is None and
        timezone is None and language is None
    )

    if name is not None and name.strip() != project.name:
        changes["name"] = {"old": project.name, "new": name.strip()}
        project.name = name.strip()

    if slug is not None:
        new_slug = slugify_text(slug)
        if new_slug != project.slug:
            existing = await get_project_by_slug_async(db, project.organization_id, new_slug)
            if existing and existing.id != project.id:
                raise ConflictException(f"Project with slug '{new_slug}' already exists in this organization")
            changes["slug"] = {"old": project.slug, "new": new_slug}
            project.slug = new_slug

    if description is not None:
        changes["description"] = description
        project.description = description

    if status is not None and status != project.status:
        changes["status"] = {"old": project.status, "new": status}
        project.status = status

    if color is not None:
        changes["color"] = color
        project.color = color

    if icon is not None:
        changes["icon"] = icon
        project.icon = icon

    if timezone is not None:
        changes["timezone"] = timezone
        project.timezone = timezone

    if language is not None:
        changes["language"] = language
        project.language = language

    if settings is not None:
        changes["settings"] = settings
        project.settings = settings

    project.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(project)

    action_name = "settings.changed" if is_settings_only else "project.updated"

    await log_audit_event_async(
        db,
        action=action_name,
        user_id=actor_id,
        organization_id=project.organization_id,
        target_resource=f"project:{project.id}",
        ip_address=ip_address,
        user_agent=user_agent,
        details=changes
    )
    await create_org_audit_event_async(
        db,
        org_id=project.organization_id,
        action=action_name,
        actor_id=actor_id,
        details={"project_id": project.id, "changes": changes}
    )

    return project


async def archive_project_async(
    db: AsyncSession,
    project: Project,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Project:
    project.archived = True
    project.status = "archived"
    project.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(project)

    await log_audit_event_async(
        db,
        action="project.archived",
        user_id=actor_id,
        organization_id=project.organization_id,
        target_resource=f"project:{project.id}",
        ip_address=ip_address,
        user_agent=user_agent,
        details={"project_id": project.id, "name": project.name}
    )
    await create_org_audit_event_async(
        db,
        org_id=project.organization_id,
        action="project.archived",
        actor_id=actor_id,
        details={"project_id": project.id, "name": project.name}
    )
    return project


async def restore_project_async(
    db: AsyncSession,
    project: Project,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Project:
    project.archived = False
    project.status = "active"
    project.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(project)

    await log_audit_event_async(
        db,
        action="project.restored",
        user_id=actor_id,
        organization_id=project.organization_id,
        target_resource=f"project:{project.id}",
        ip_address=ip_address,
        user_agent=user_agent,
        details={"project_id": project.id, "name": project.name}
    )
    await create_org_audit_event_async(
        db,
        org_id=project.organization_id,
        action="project.restored",
        actor_id=actor_id,
        details={"project_id": project.id, "name": project.name}
    )
    return project


async def delete_project_async(
    db: AsyncSession,
    project: Project,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    p_id = project.id
    org_id = project.organization_id
    p_name = project.name

    await log_audit_event_async(
        db,
        action="project.deleted",
        user_id=actor_id,
        organization_id=org_id,
        target_resource=f"project:{p_id}",
        ip_address=ip_address,
        user_agent=user_agent,
        details={"project_id": p_id, "name": p_name}
    )
    await create_org_audit_event_async(
        db,
        org_id=org_id,
        action="project.deleted",
        actor_id=actor_id,
        details={"project_id": p_id, "name": p_name}
    )

    await db.delete(project)
    await db.commit()


async def get_project_activity_async(
    db: AsyncSession,
    project_id: int,
    limit: int = 50
) -> List[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(
            or_(
                AuditLog.target_resource == f"project:{project_id}",
                AuditLog.details["project_id"].as_integer() == project_id
            )
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --- MEMBERSHIP CRUD ---

async def get_membership_async(db: AsyncSession, org_id: int, user_id: int) -> Optional[Membership]:
    stmt = select(Membership).where(
        Membership.organization_id == org_id,
        Membership.user_id == user_id
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_org_members_async(db: AsyncSession, org_id: int) -> List[Membership]:
    stmt = (
        select(Membership)
        .options(joinedload(Membership.user))
        .where(Membership.organization_id == org_id)
        .order_by(Membership.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_member_role_async(
    db: AsyncSession,
    org_id: int,
    user_id: int,
    new_role: str,
    actor_id: Optional[int] = None
) -> Optional[Membership]:
    membership = await get_membership_async(db, org_id, user_id)
    if not membership:
        return None

    old_role = membership.role
    membership.role = new_role
    membership.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(membership)

    await create_org_audit_event_async(
        db,
        org_id=org_id,
        action="member.role_updated",
        actor_id=actor_id,
        details={"target_user_id": user_id, "old_role": old_role, "new_role": new_role}
    )

    return membership


async def remove_org_member_async(
    db: AsyncSession,
    org_id: int,
    user_id: int,
    actor_id: Optional[int] = None
) -> bool:
    membership = await get_membership_async(db, org_id, user_id)
    if not membership:
        return False

    await db.delete(membership)
    await db.commit()

    await create_org_audit_event_async(
        db,
        org_id=org_id,
        action="member.removed",
        actor_id=actor_id,
        details={"target_user_id": user_id, "removed_role": membership.role}
    )

    return True


async def transfer_org_ownership_async(
    db: AsyncSession,
    org_id: int,
    current_owner_id: int,
    new_owner_id: int
) -> bool:
    current_owner_mem = await get_membership_async(db, org_id, current_owner_id)
    new_owner_mem = await get_membership_async(db, org_id, new_owner_id)

    if not current_owner_mem or current_owner_mem.role != "Owner":
        return False
    if not new_owner_mem:
        return False

    current_owner_mem.role = "Admin"
    new_owner_mem.role = "Owner"
    current_owner_mem.updated_at = datetime.utcnow()
    new_owner_mem.updated_at = datetime.utcnow()

    await db.commit()

    await create_org_audit_event_async(
        db,
        org_id=org_id,
        action="ownership.transferred",
        actor_id=current_owner_id,
        details={"previous_owner_id": current_owner_id, "new_owner_id": new_owner_id}
    )

    return True


# --- INVITATION CRUD ---

async def create_invitation_async(
    db: AsyncSession,
    org_id: int,
    email: str,
    role: str,
    token: str,
    invited_by_id: int,
    expires_at: datetime
) -> Invitation:
    invitation = Invitation(
        organization_id=org_id,
        email=email.lower().strip(),
        role=role,
        token=token,
        status="pending",
        invited_by_id=invited_by_id,
        expires_at=expires_at
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    await create_org_audit_event_async(
        db,
        org_id=org_id,
        action="member.invited",
        actor_id=invited_by_id,
        details={"email": email, "role": role}
    )

    return invitation


async def get_invitation_by_token_async(db: AsyncSession, token: str) -> Optional[Invitation]:
    stmt = select(Invitation).where(
        Invitation.token == token,
        Invitation.status == "pending",
        Invitation.expires_at > datetime.utcnow()
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_org_invitations_async(db: AsyncSession, org_id: int) -> List[Invitation]:
    stmt = select(Invitation).where(
        Invitation.organization_id == org_id,
        Invitation.status == "pending"
    ).order_by(Invitation.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def accept_invitation_async(
    db: AsyncSession,
    invitation: Invitation,
    user: User
) -> Membership:
    invitation.status = "accepted"

    existing = await get_membership_async(db, invitation.organization_id, user.id)
    if existing:
        existing.role = invitation.role
        membership = existing
    else:
        membership = Membership(
            organization_id=invitation.organization_id,
            user_id=user.id,
            role=invitation.role
        )
        db.add(membership)

    await db.commit()
    await db.refresh(membership)

    await create_org_audit_event_async(
        db,
        org_id=invitation.organization_id,
        action="invitation.accepted",
        actor_id=user.id,
        details={"email": user.email, "role": invitation.role}
    )

    return membership


async def reject_invitation_async(
    db: AsyncSession,
    invitation: Invitation,
    user: User
) -> None:
    invitation.status = "rejected"
    await db.commit()

    await create_org_audit_event_async(
        db,
        org_id=invitation.organization_id,
        action="invitation.rejected",
        actor_id=user.id,
        details={"email": user.email}
    )


async def cancel_invitation_async(
    db: AsyncSession,
    invitation: Invitation,
    actor_id: Optional[int] = None
) -> None:
    invitation.status = "cancelled"
    await db.commit()

    await create_org_audit_event_async(
        db,
        org_id=invitation.organization_id,
        action="invitation.cancelled",
        actor_id=actor_id,
        details={"email": invitation.email}
    )




# --- WEBSITE CRUD (STRICTLY TENANT ISOLATED) ---
def get_user_websites(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    sort_by: str = "id",
    order: str = "asc"
) -> List[Website]:
    """Retrieve ONLY websites owned by the specified user_id with pagination, sorting, and search."""
    query = db.query(Website).options(joinedload(Website.owner)).filter(Website.user_id == user_id)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Website.domain.ilike(pattern)) |
            (Website.url.ilike(pattern)) |
            (Website.company_name.ilike(pattern))
        )

    sort_attr = getattr(Website, sort_by, Website.id) if hasattr(Website, sort_by) else Website.id
    if order.lower() == "desc":
        query = query.order_by(sort_attr.desc())
    else:
        query = query.order_by(sort_attr.asc())

    return paginate(query, skip=skip, limit=limit)

async def get_user_websites_async(
    db: AsyncSession,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    sort_by: str = "id",
    order: str = "asc"
) -> List[Website]:
    stmt = select(Website).options(selectinload(Website.owner)).where(Website.user_id == user_id)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Website.domain.ilike(pattern),
                Website.url.ilike(pattern),
                Website.company_name.ilike(pattern)
            )
        )

    sort_attr = getattr(Website, sort_by, Website.id) if hasattr(Website, sort_by) else Website.id
    if order.lower() == "desc":
        stmt = stmt.order_by(sort_attr.desc())
    else:
        stmt = stmt.order_by(sort_attr.asc())

    return await async_paginate(db, stmt, skip=skip, limit=limit)

def get_website_by_id(db: Session, website_id: int, user_id: int) -> Optional[Website]:
    """Retrieve a website if and ONLY if it belongs to user_id."""
    return db.query(Website).options(joinedload(Website.owner)).filter(
        Website.id == website_id, Website.user_id == user_id
    ).first()

async def get_website_by_id_async(db: AsyncSession, website_id: int, user_id: int) -> Optional[Website]:
    stmt = select(Website).options(selectinload(Website.owner)).where(
        Website.id == website_id, Website.user_id == user_id
    )
    result = await db.execute(stmt)
    return result.scalars().first()

def get_website_by_id_unfiltered(db: Session, website_id: int) -> Optional[Website]:
    """Retrieve website strictly for ownership checking (returns record regardless of owner)."""
    return db.query(Website).options(joinedload(Website.owner)).filter(Website.id == website_id).first()

async def get_website_by_id_unfiltered_async(db: AsyncSession, website_id: int) -> Optional[Website]:
    stmt = select(Website).options(selectinload(Website.owner)).where(Website.id == website_id)
    result = await db.execute(stmt)
    return result.scalars().first()

def get_website_by_domain_unfiltered(db: Session, domain: str) -> Optional[Website]:
    """Retrieve website by domain regardless of owner for domain-level collision/ownership checking."""
    clean_domain = domain.replace("https://", "").replace("http://", "").split("/")[0].lower()
    return db.query(Website).options(joinedload(Website.owner)).filter(Website.domain == clean_domain).first()

async def get_website_by_domain_unfiltered_async(db: AsyncSession, domain: str) -> Optional[Website]:
    clean_domain = domain.replace("https://", "").replace("http://", "").split("/")[0].lower()
    stmt = select(Website).options(selectinload(Website.owner)).where(Website.domain == clean_domain)
    result = await db.execute(stmt)
    return result.scalars().first()

def create_website(db: Session, user_id: int, url: str, domain: str, company_name: Optional[str] = None) -> Website:
    norm = normalize_domain(domain)
    website = Website(user_id=user_id, owner_id=user_id, url=url, domain=domain, normalized_domain=norm, company_name=company_name)
    db.add(website)
    db.commit()
    db.refresh(website)
    return website

async def create_website_async(db: AsyncSession, user_id: int, url: str, domain: str, company_name: Optional[str] = None) -> Website:
    norm = normalize_domain(domain)
    website = Website(user_id=user_id, owner_id=user_id, url=url, domain=domain, normalized_domain=norm, company_name=company_name)
    db.add(website)
    await db.commit()
    await db.refresh(website)
    return website

def delete_website_instance(db: Session, website: Website) -> None:
    """Delete website instance directly without extra DB lookup."""
    db.delete(website)
    db.commit()

async def delete_website_instance_async(db: AsyncSession, website: Website) -> None:
    await db.delete(website)
    await db.commit()

def delete_user_website(db: Session, website_id: int, user_id: int) -> bool:
    """Delete website ONLY if owned by user_id."""
    website = get_website_by_id(db, website_id, user_id)
    if not website:
        return False
    delete_website_instance(db, website)
    return True

async def delete_user_website_async(db: AsyncSession, website_id: int, user_id: int) -> bool:
    website = await get_website_by_id_async(db, website_id, user_id)
    if not website:
        return False
    await delete_website_instance_async(db, website)
    return True


# --- AUDIT CRUD (STRICTLY TENANT ISOLATED) ---
def get_audit_by_id_unfiltered(db: Session, audit_id: int) -> Optional[AuditResult]:
    """Retrieve audit strictly for ownership validation with relationship eager loading."""
    return db.query(AuditResult).options(joinedload(AuditResult.website)).filter(AuditResult.id == audit_id).first()

async def get_audit_by_id_unfiltered_async(db: AsyncSession, audit_id: int) -> Optional[AuditResult]:
    stmt = select(AuditResult).options(selectinload(AuditResult.website)).where(AuditResult.id == audit_id)
    result = await db.execute(stmt)
    return result.scalars().first()

def get_user_audits_for_website(
    db: Session,
    website_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "id",
    order: str = "desc"
) -> List[AuditResult]:
    """Retrieve audits for a website if and ONLY if owned by user_id with pagination and sorting."""
    query = db.query(AuditResult).options(joinedload(AuditResult.website)).filter(
        AuditResult.website_id == website_id,
        AuditResult.user_id == user_id
    )

    sort_attr = getattr(AuditResult, sort_by, AuditResult.id) if hasattr(AuditResult, sort_by) else AuditResult.id
    if order.lower() == "asc":
        query = query.order_by(sort_attr.asc())
    else:
        query = query.order_by(sort_attr.desc())

    return paginate(query, skip=skip, limit=limit)

async def get_user_audits_for_website_async(
    db: AsyncSession,
    website_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "id",
    order: str = "desc"
) -> List[AuditResult]:
    stmt = select(AuditResult).options(selectinload(AuditResult.website)).where(
        AuditResult.website_id == website_id,
        AuditResult.user_id == user_id
    )

    sort_attr = getattr(AuditResult, sort_by, AuditResult.id) if hasattr(AuditResult, sort_by) else AuditResult.id
    if order.lower() == "asc":
        stmt = stmt.order_by(sort_attr.asc())
    else:
        stmt = stmt.order_by(sort_attr.desc())

    return await async_paginate(db, stmt, skip=skip, limit=limit)

def create_audit(db: Session, website_id: int, user_id: int, score: int, title: str, meta_description: str,
                 h1_tags: List[str], canonical_url: str, images_count: int, images_without_alt: int,
                 broken_links_count: int) -> AuditResult:
    audit = AuditResult(
        website_id=website_id,
        user_id=user_id,
        score=score,
        title=title,
        title_length=len(title) if title else 0,
        meta_description=meta_description,
        meta_description_length=len(meta_description) if meta_description else 0,
        h1_tags=h1_tags,
        canonical_url=canonical_url,
        viewport="width=device-width, initial-scale=1.0",
        images_count=images_count,
        images_without_alt=images_without_alt,
        has_structured_data=True,
        has_sitemap=True,
        has_robots_txt=True,
        broken_links_count=broken_links_count
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit

async def create_audit_async(db: AsyncSession, website_id: int, user_id: int, score: int, title: str, meta_description: str,
                       h1_tags: List[str], canonical_url: str, images_count: int, images_without_alt: int,
                       broken_links_count: int) -> AuditResult:
    audit = AuditResult(
        website_id=website_id,
        user_id=user_id,
        score=score,
        title=title,
        title_length=len(title) if title else 0,
        meta_description=meta_description,
        meta_description_length=len(meta_description) if meta_description else 0,
        h1_tags=h1_tags,
        canonical_url=canonical_url,
        viewport="width=device-width, initial-scale=1.0",
        images_count=images_count,
        images_without_alt=images_without_alt,
        has_structured_data=True,
        has_sitemap=True,
        has_robots_txt=True,
        broken_links_count=broken_links_count
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)
    return audit


# --- LEADS CRUD (STRICTLY TENANT ISOLATED) ---
def get_user_leads_for_website(
    db: Session,
    website_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    source: Optional[str] = None,
    sort_by: str = "id",
    order: str = "desc"
) -> List[Lead]:
    query = db.query(Lead).options(joinedload(Lead.website)).filter(
        Lead.website_id == website_id,
        Lead.user_id == user_id
    )
    if source:
        query = query.filter(Lead.source == source)

    sort_attr = getattr(Lead, sort_by, Lead.id) if hasattr(Lead, sort_by) else Lead.id
    if order.lower() == "asc":
        query = query.order_by(sort_attr.asc())
    else:
        query = query.order_by(sort_attr.desc())

    return paginate(query, skip=skip, limit=limit)

async def get_user_leads_for_website_async(
    db: AsyncSession,
    website_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    source: Optional[str] = None,
    sort_by: str = "id",
    order: str = "desc"
) -> List[Lead]:
    stmt = select(Lead).options(selectinload(Lead.website)).where(
        Lead.website_id == website_id,
        Lead.user_id == user_id
    )
    if source:
        stmt = stmt.where(Lead.source == source)

    sort_attr = getattr(Lead, sort_by, Lead.id) if hasattr(Lead, sort_by) else Lead.id
    if order.lower() == "asc":
        stmt = stmt.order_by(sort_attr.asc())
    else:
        stmt = stmt.order_by(sort_attr.desc())

    return await async_paginate(db, stmt, skip=skip, limit=limit)

def create_lead(db: Session, website_id: int, user_id: int, email: str, source: str = "audit") -> Lead:
    lead = Lead(website_id=website_id, user_id=user_id, email=email, source=source)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead

async def create_lead_async(db: AsyncSession, website_id: int, user_id: int, email: str, source: str = "audit") -> Lead:
    lead = Lead(website_id=website_id, user_id=user_id, email=email, source=source)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


# --- REPORTS CRUD (STRICTLY TENANT ISOLATED) ---
def get_user_reports_for_website(
    db: Session,
    website_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    format: Optional[str] = None,
    sort_by: str = "id",
    order: str = "desc"
) -> List[Report]:
    query = db.query(Report).options(joinedload(Report.website)).filter(
        Report.website_id == website_id,
        Report.user_id == user_id
    )
    if format:
        query = query.filter(Report.format == format)

    sort_attr = getattr(Report, sort_by, Report.id) if hasattr(Report, sort_by) else Report.id
    if order.lower() == "asc":
        query = query.order_by(sort_attr.asc())
    else:
        query = query.order_by(sort_attr.desc())

    return paginate(query, skip=skip, limit=limit)

async def get_user_reports_for_website_async(
    db: AsyncSession,
    website_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    format: Optional[str] = None,
    sort_by: str = "id",
    order: str = "desc"
) -> List[Report]:
    stmt = select(Report).options(selectinload(Report.website)).where(
        Report.website_id == website_id,
        Report.user_id == user_id
    )
    if format:
        stmt = stmt.where(Report.format == format)

    sort_attr = getattr(Report, sort_by, Report.id) if hasattr(Report, sort_by) else Report.id
    if order.lower() == "asc":
        stmt = stmt.order_by(sort_attr.asc())
    else:
        stmt = stmt.order_by(sort_attr.desc())

    return await async_paginate(db, stmt, skip=skip, limit=limit)

def create_report(db: Session, website_id: int, user_id: int, title: str, format: str = "pdf") -> Report:
    report = Report(website_id=website_id, user_id=user_id, title=title, format=format)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report

async def create_report_async(db: AsyncSession, website_id: int, user_id: int, title: str, format: str = "pdf") -> Report:
    report = Report(website_id=website_id, user_id=user_id, title=title, format=format)
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


# --- JOBS CRUD (STRICTLY TENANT ISOLATED) ---
def get_job_by_id_unfiltered(db: Session, job_id: int) -> Optional[Job]:
    """Retrieve job strictly for ownership verification with relationship eager loading."""
    return db.query(Job).options(joinedload(Job.website)).filter(Job.id == job_id).first()

async def get_job_by_id_unfiltered_async(db: AsyncSession, job_id: int) -> Optional[Job]:
    stmt = select(Job).options(selectinload(Job.website)).where(Job.id == job_id)
    result = await db.execute(stmt)
    return result.scalars().first()

def get_user_job_by_id(db: Session, job_id: int, user_id: int) -> Optional[Job]:
    """Retrieve job if and ONLY if it belongs to user_id with eager relationship loading."""
    return db.query(Job).options(joinedload(Job.website)).filter(Job.id == job_id, Job.user_id == user_id).first()

async def get_user_job_by_id_async(db: AsyncSession, job_id: int, user_id: int) -> Optional[Job]:
    stmt = select(Job).options(selectinload(Job.website)).where(Job.id == job_id, Job.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()

def get_user_jobs(
    db: Session,
    user_id: int,
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    website_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    order: str = "desc"
) -> List[Job]:
    """Retrieve jobs owned exclusively by user_id with optional filtering, sorting, eager loading, and pagination."""
    query = db.query(Job).options(joinedload(Job.website)).filter(Job.user_id == user_id)
    if job_type:
        query = query.filter(Job.job_type == job_type)
    if status:
        query = query.filter(Job.status == status)
    if website_id is not None:
        query = query.filter(Job.website_id == website_id)

    sort_attr = getattr(Job, sort_by, Job.created_at) if hasattr(Job, sort_by) else Job.created_at
    if order.lower() == "asc":
        query = query.order_by(sort_attr.asc())
    else:
        query = query.order_by(sort_attr.desc())

    return paginate(query, skip=skip, limit=limit)

async def get_user_jobs_async(
    db: AsyncSession,
    user_id: int,
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    website_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    order: str = "desc"
) -> List[Job]:
    stmt = select(Job).options(selectinload(Job.website)).where(Job.user_id == user_id)
    if job_type:
        stmt = stmt.where(Job.job_type == job_type)
    if status:
        stmt = stmt.where(Job.status == status)
    if website_id is not None:
        stmt = stmt.where(Job.website_id == website_id)

    sort_attr = getattr(Job, sort_by, Job.created_at) if hasattr(Job, sort_by) else Job.created_at
    if order.lower() == "asc":
        stmt = stmt.order_by(sort_attr.asc())
    else:
        stmt = stmt.order_by(sort_attr.desc())

    return await async_paginate(db, stmt, skip=skip, limit=limit)

def create_job(db: Session, user_id: int, job_type: str, website_id: Optional[int] = None, result_reference: Optional[dict] = None) -> Job:
    """Create a new job record for user_id."""
    job = Job(
        user_id=user_id,
        website_id=website_id,
        job_type=job_type,
        status="pending",
        progress=0,
        result_reference=result_reference,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

async def create_job_async(db: AsyncSession, user_id: int, job_type: str, website_id: Optional[int] = None, result_reference: Optional[dict] = None) -> Job:
    job = Job(
        user_id=user_id,
        website_id=website_id,
        job_type=job_type,
        status="pending",
        progress=0,
        result_reference=result_reference,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job

def update_job(db: Session, job: Job, status: Optional[str] = None, progress: Optional[int] = None,
               error_message: Optional[str] = None, result_reference: Optional[dict] = None,
               started_at: Optional[datetime] = None, finished_at: Optional[datetime] = None) -> Job:
    """Update job fields safely in place without redundant refresh SELECT queries."""
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = progress
    if error_message is not None:
        job.error_message = error_message
    if result_reference is not None:
        job.result_reference = result_reference
    if started_at is not None:
        job.started_at = started_at
    if finished_at is not None:
        job.finished_at = finished_at
    job.updated_at = datetime.utcnow()
    db.commit()
    return job

async def update_job_async(db: AsyncSession, job: Job, status: Optional[str] = None, progress: Optional[int] = None,
                     error_message: Optional[str] = None, result_reference: Optional[dict] = None,
                     started_at: Optional[datetime] = None, finished_at: Optional[datetime] = None) -> Job:
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = progress
    if error_message is not None:
        job.error_message = error_message
    if result_reference is not None:
        job.result_reference = result_reference
    if started_at is not None:
        job.started_at = started_at
    if finished_at is not None:
        job.finished_at = finished_at
    job.updated_at = datetime.utcnow()
    await db.commit()
    return job

def delete_job_instance(db: Session, job: Job) -> None:
    """Delete job instance directly without extra DB lookup."""
    db.delete(job)
    db.commit()

async def delete_job_instance_async(db: AsyncSession, job: Job) -> None:
    await db.delete(job)
    await db.commit()

def delete_user_job(db: Session, job_id: int, user_id: int) -> bool:
    """Delete job ONLY if owned by user_id."""
    job = get_user_job_by_id(db, job_id, user_id)
    if not job:
        return False
    delete_job_instance(db, job)
    return True

async def delete_user_job_async(db: AsyncSession, job_id: int, user_id: int) -> bool:
    job = await get_user_job_by_id_async(db, job_id, user_id)
    if not job:
        return False
    await delete_job_instance_async(db, job)
    return True

def get_stale_jobs(db: Session, max_age_seconds: int = 300) -> List[Job]:
    """Retrieve running or pending jobs that haven't been updated within max_age_seconds using composite index."""
    cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)
    return db.query(Job).options(joinedload(Job.website)).filter(
        Job.status.in_(["running", "pending"]),
        Job.updated_at < cutoff
    ).all()

async def get_stale_jobs_async(db: AsyncSession, max_age_seconds: int = 300) -> List[Job]:
    cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)
    stmt = select(Job).options(selectinload(Job.website)).where(
        Job.status.in_(["running", "pending"]),
        Job.updated_at < cutoff
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --- RELATIONSHIP EAGER LOADING (SELECTINLOAD / JOINEDLOAD TO ELIMINATE N+1 QUERIES) ---
def get_user_with_relations(db: Session, user_id: int) -> Optional[User]:
    """Retrieve user with selectinload on collection relationships (websites, audits, jobs)."""
    return db.query(User).options(
        selectinload(User.websites),
        selectinload(User.audits),
        selectinload(User.jobs)
    ).filter(User.id == user_id).first()

async def get_user_with_relations_async(db: AsyncSession, user_id: int) -> Optional[User]:
    stmt = select(User).options(
        selectinload(User.websites),
        selectinload(User.audits),
        selectinload(User.jobs)
    ).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()

def get_website_with_details(db: Session, website_id: int, user_id: int) -> Optional[Website]:
    """Retrieve website with selectinload on collections and joinedload on owner to prevent N+1 queries."""
    return db.query(Website).options(
        joinedload(Website.owner),
        selectinload(Website.audits),
        selectinload(Website.leads),
        selectinload(Website.reports),
        selectinload(Website.jobs)
    ).filter(Website.id == website_id, Website.user_id == user_id).first()

async def get_website_with_details_async(db: AsyncSession, website_id: int, user_id: int) -> Optional[Website]:
    stmt = select(Website).options(
        joinedload(Website.owner),
        selectinload(Website.audits),
        selectinload(Website.leads),
        selectinload(Website.reports),
        selectinload(Website.jobs)
    ).where(Website.id == website_id, Website.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()


# --- BULK INSERTS AND BULK UPDATES ---
def bulk_create_keywords(db: Session, user_id: int, items: List[Dict[str, Any]]) -> List[KeywordResult]:
    """Perform bulk insert of keyword results to optimize write throughput."""
    if not items:
        return []
    records = []
    for item in items:
        record = KeywordResult(
            user_id=user_id,
            seed_keyword=item.get("seed_keyword", ""),
            keyword=item.get("keyword", ""),
            intent=item.get("intent", "Informational"),
            volume=item.get("volume", 0),
            kd=item.get("kd", 0),
            cpc=str(item.get("cpc", "0.00")),
            cluster=item.get("cluster", "General")
        )
        records.append(record)
    db.add_all(records)
    db.commit()
    return records

async def bulk_create_keywords_async(db: AsyncSession, user_id: int, items: List[Dict[str, Any]]) -> List[KeywordResult]:
    """Perform bulk insert of keyword results asynchronously."""
    if not items:
        return []
    records = []
    for item in items:
        record = KeywordResult(
            user_id=user_id,
            seed_keyword=item.get("seed_keyword", ""),
            keyword=item.get("keyword", ""),
            intent=item.get("intent", "Informational"),
            volume=item.get("volume", 0),
            kd=item.get("kd", 0),
            cpc=str(item.get("cpc", "0.00")),
            cluster=item.get("cluster", "General")
        )
        records.append(record)
    db.add_all(records)
    await db.commit()
    return records

def bulk_create_leads(db: Session, user_id: int, website_id: Optional[int], items: List[Dict[str, Any]]) -> List[Lead]:
    """Perform bulk insert of lead records."""
    if not items:
        return []
    records = []
    for item in items:
        record = Lead(
            user_id=user_id,
            website_id=website_id,
            email=item.get("email"),
            phone=item.get("phone"),
            source=item.get("source", "audit")
        )
        records.append(record)
    db.add_all(records)
    db.commit()
    return records

async def bulk_create_leads_async(db: AsyncSession, user_id: int, website_id: Optional[int], items: List[Dict[str, Any]]) -> List[Lead]:
    if not items:
        return []
    records = []
    for item in items:
        record = Lead(
            user_id=user_id,
            website_id=website_id,
            email=item.get("email"),
            phone=item.get("phone"),
            source=item.get("source", "audit")
        )
        records.append(record)
    db.add_all(records)
    await db.commit()
    return records

def bulk_create_rank_checks(db: Session, user_id: int, items: List[Dict[str, Any]]) -> List[RankCheck]:
    """Perform bulk insert of rank check results."""
    if not items:
        return []
    records = []
    for item in items:
        record = RankCheck(
            user_id=user_id,
            website_id=item.get("website_id"),
            keyword=item.get("keyword"),
            domain=item.get("domain"),
            position=item.get("position", 100),
            checked_results=item.get("checked_results", 30),
            source=item.get("source", "free_tracker")
        )
        records.append(record)
    db.add_all(records)
    db.commit()
    return records

async def bulk_create_rank_checks_async(db: AsyncSession, user_id: int, items: List[Dict[str, Any]]) -> List[RankCheck]:
    if not items:
        return []
    records = []
    for item in items:
        record = RankCheck(
            user_id=user_id,
            website_id=item.get("website_id"),
            keyword=item.get("keyword"),
            domain=item.get("domain"),
            position=item.get("position", 100),
            checked_results=item.get("checked_results", 30),
            source=item.get("source", "free_tracker")
        )
        records.append(record)
    db.add_all(records)
    await db.commit()
    return records

def bulk_update_jobs_status(
    db: Session,
    job_ids: List[int],
    status: str,
    progress: Optional[int] = None,
    error_message: Optional[str] = None
) -> int:
    """Perform bulk update of job statuses in a single SQL UPDATE query."""
    if not job_ids:
        return 0
    values: Dict[str, Any] = {"status": status, "updated_at": datetime.utcnow()}
    if progress is not None:
        values["progress"] = progress
    if error_message is not None:
        values["error_message"] = error_message

    stmt = update(Job).where(Job.id.in_(job_ids)).values(**values)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount

async def bulk_update_jobs_status_async(
    db: AsyncSession,
    job_ids: List[int],
    status: str,
    progress: Optional[int] = None,
    error_message: Optional[str] = None
) -> int:
    """Perform bulk update of job statuses asynchronously in a single SQL UPDATE query."""
    if not job_ids:
        return 0
    values: Dict[str, Any] = {"status": status, "updated_at": datetime.utcnow()}
    if progress is not None:
        values["progress"] = progress
    if error_message is not None:
        values["error_message"] = error_message

    stmt = update(Job).where(Job.id.in_(job_ids)).values(**values)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


# --- CURSOR-BASED PAGINATION CRUD FUNCTIONS ---
def get_user_websites_cursor(
    db: Session,
    user_id: int,
    cursor: Optional[str] = None,
    limit: int = 50,
    order: str = "desc"
) -> Tuple[List[Website], Optional[str], bool]:
    """Retrieve user websites using cursor pagination."""
    query = db.query(Website).options(joinedload(Website.owner)).filter(Website.user_id == user_id)
    return cursor_paginate(query, column=Website.id, cursor=cursor, limit=limit, order=order)

async def get_user_websites_cursor_async(
    db: AsyncSession,
    user_id: int,
    cursor: Optional[str] = None,
    limit: int = 50,
    order: str = "desc"
) -> Tuple[List[Website], Optional[str], bool]:
    stmt = select(Website).options(selectinload(Website.owner)).where(Website.user_id == user_id)
    return await async_cursor_paginate(db, stmt, column=Website.id, cursor=cursor, limit=limit, order=order)

async def get_user_audits_cursor_async(
    db: AsyncSession,
    website_id: int,
    user_id: int,
    cursor: Optional[str] = None,
    limit: int = 50,
    order: str = "desc"
) -> Tuple[List[AuditResult], Optional[str], bool]:
    """Retrieve audit results using cursor pagination."""
    stmt = select(AuditResult).options(selectinload(AuditResult.website)).where(
        AuditResult.website_id == website_id,
        AuditResult.user_id == user_id
    )
    return await async_cursor_paginate(db, stmt, column=AuditResult.id, cursor=cursor, limit=limit, order=order)

async def get_user_jobs_cursor_async(
    db: AsyncSession,
    user_id: int,
    cursor: Optional[str] = None,
    limit: int = 50,
    order: str = "desc"
) -> Tuple[List[Job], Optional[str], bool]:
    """Retrieve jobs using cursor pagination."""
    stmt = select(Job).options(selectinload(Job.website)).where(Job.user_id == user_id)
    return await async_cursor_paginate(db, stmt, column=Job.id, cursor=cursor, limit=limit, order=order)

async def get_user_leads_cursor_async(
    db: AsyncSession,
    website_id: int,
    user_id: int,
    cursor: Optional[str] = None,
    limit: int = 50,
    order: str = "desc"
) -> Tuple[List[Lead], Optional[str], bool]:
    """Retrieve leads using cursor pagination."""
    stmt = select(Lead).options(selectinload(Lead.website)).where(
        Lead.website_id == website_id,
        Lead.user_id == user_id
    )
    return await async_cursor_paginate(db, stmt, column=Lead.id, cursor=cursor, limit=limit, order=order)


# --- WEBSITE DOMAIN & PROJECT MANAGEMENT CRUD ---

DOMAIN_REGEX = re.compile(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$')

def normalize_domain(domain: str) -> str:
    if not domain:
        return ""
    d = domain.strip().lower()
    if "://" in d:
        d = d.split("://", 1)[1]
    d = d.split("/", 1)[0]
    d = d.split("?", 1)[0]
    d = d.split("#", 1)[0]
    d = d.split(":", 1)[0]
    if d.startswith("www."):
        d = d[4:]
    return d.strip()

def is_valid_domain(domain: str) -> bool:
    if not domain or len(domain) > 253:
        return False
    norm = normalize_domain(domain)
    if not norm:
        return False
    if norm == "localhost":
        return True
    return bool(DOMAIN_REGEX.match(norm))

async def get_org_website_by_normalized_domain_async(
    db: AsyncSession,
    organization_id: int,
    normalized_domain: str,
    exclude_website_id: Optional[int] = None
) -> Optional[Website]:
    stmt = select(Website).where(
        Website.organization_id == organization_id,
        Website.normalized_domain == normalized_domain
    )
    if exclude_website_id:
        stmt = stmt.where(Website.id != exclude_website_id)
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_project_website_by_id_or_domain_async(
    db: AsyncSession,
    project_id: int,
    website_id_or_domain: str
) -> Optional[Website]:
    norm_search = normalize_domain(website_id_or_domain)
    if website_id_or_domain.isdigit():
        stmt = select(Website).where(
            Website.project_id == project_id,
            or_(
                Website.id == int(website_id_or_domain),
                Website.domain == website_id_or_domain,
                Website.normalized_domain == norm_search
            )
        )
    else:
        stmt = select(Website).where(
            Website.project_id == project_id,
            or_(
                Website.domain == website_id_or_domain,
                Website.normalized_domain == norm_search
            )
        )
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_project_websites_async(
    db: AsyncSession,
    project_id: int,
    search: Optional[str] = None,
    status: Optional[str] = None,
    archived: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50
) -> Tuple[List[Website], int]:
    stmt = select(Website).where(Website.project_id == project_id)
    count_stmt = select(func.count(Website.id)).where(Website.project_id == project_id)

    if search:
        pattern = f"%{search}%"
        norm_pat = f"%{normalize_domain(search)}%"
        cond = or_(
            Website.domain.ilike(pattern),
            Website.normalized_domain.ilike(norm_pat),
            Website.company_name.ilike(pattern)
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    if status:
        stmt = stmt.where(Website.status == status)
        count_stmt = count_stmt.where(Website.status == status)

    if archived is not None:
        stmt = stmt.where(Website.archived == archived)
        count_stmt = count_stmt.where(Website.archived == archived)

    stmt = stmt.order_by(Website.created_at.desc()).offset(skip).limit(limit)

    total_res = await db.execute(count_stmt)
    total = total_res.scalar_one()

    items_res = await db.execute(stmt)
    items = list(items_res.scalars().all())

    return items, total

async def create_project_website_async(
    db: AsyncSession,
    project_id: int,
    organization_id: int,
    owner_id: int,
    domain: str,
    protocol: str = "https",
    status: str = "active",
    verification_status: str = "unverified",
    favicon: Optional[str] = None,
    country: Optional[str] = None,
    language: str = "en",
    timezone: str = "UTC",
    settings: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Website:
    norm_domain = normalize_domain(domain)
    existing = await get_org_website_by_normalized_domain_async(db, organization_id, norm_domain)
    if existing:
        raise ConflictException(f"Website with domain '{norm_domain}' already exists in this organization")

    clean_protocol = (protocol or "https").lower().replace("://", "").strip()
    full_url = f"{clean_protocol}://{norm_domain}"
    settings_dict = settings or {}

    website = Website(
        project_id=project_id,
        organization_id=organization_id,
        owner_id=owner_id,
        user_id=owner_id,
        domain=norm_domain,
        normalized_domain=norm_domain,
        protocol=clean_protocol,
        status=status or "active",
        verification_status=verification_status or "unverified",
        favicon=favicon,
        country=country,
        language=language or "en",
        timezone=timezone or "UTC",
        settings=settings_dict,
        url=full_url,
        company_name=norm_domain.split('.')[0].upper(),
        archived=False
    )
    db.add(website)
    await db.commit()
    await db.refresh(website)

    await log_audit_event_async(
        db,
        action="website.created",
        user_id=owner_id,
        organization_id=organization_id,
        target_resource=f"website:{website.id}",
        ip_address=ip_address,
        user_agent=user_agent,
        details={"website_id": website.id, "project_id": project_id, "domain": norm_domain}
    )
    await create_org_audit_event_async(
        db,
        org_id=organization_id,
        action="website.created",
        actor_id=owner_id,
        details={"website_id": website.id, "project_id": project_id, "domain": norm_domain}
    )

    return website

async def update_project_website_async(
    db: AsyncSession,
    website: Website,
    domain: Optional[str] = None,
    protocol: Optional[str] = None,
    status: Optional[str] = None,
    verification_status: Optional[str] = None,
    favicon: Optional[str] = None,
    country: Optional[str] = None,
    language: Optional[str] = None,
    timezone: Optional[str] = None,
    settings: Optional[dict] = None,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Website:
    changed_keys = []

    if domain is not None and domain != website.domain:
        norm_domain = normalize_domain(domain)
        existing = await get_org_website_by_normalized_domain_async(
            db, website.organization_id, norm_domain, exclude_website_id=website.id
        )
        if existing:
            raise ConflictException(f"Website with domain '{norm_domain}' already exists in this organization")
        website.domain = domain
        website.normalized_domain = norm_domain
        changed_keys.append("domain")

    if protocol is not None:
        website.protocol = protocol.lower().replace("://", "").strip()
        changed_keys.append("protocol")

    if website.normalized_domain and website.protocol:
        website.url = f"{website.protocol}://{website.normalized_domain}"

    if status is not None:
        website.status = status
        changed_keys.append("status")

    if verification_status is not None:
        website.verification_status = verification_status
        changed_keys.append("verification_status")

    if favicon is not None:
        website.favicon = favicon
        changed_keys.append("favicon")

    if country is not None:
        website.country = country
        changed_keys.append("country")

    if language is not None:
        website.language = language
        changed_keys.append("language")

    if timezone is not None:
        website.timezone = timezone
        changed_keys.append("timezone")

    settings_updated = False
    if settings is not None:
        website.settings = settings
        changed_keys.append("settings")
        settings_updated = True

    website.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(website)

    audit_action = "website.settings_changed" if (settings_updated and len(changed_keys) == 1) else "website.updated"

    await log_audit_event_async(
        db,
        action=audit_action,
        user_id=actor_id,
        organization_id=website.organization_id,
        target_resource=f"website:{website.id}",
        ip_address=ip_address,
        user_agent=user_agent,
        details={"website_id": website.id, "project_id": website.project_id, "changes": changed_keys}
    )
    await create_org_audit_event_async(
        db,
        org_id=website.organization_id,
        action=audit_action,
        actor_id=actor_id,
        details={"website_id": website.id, "project_id": website.project_id, "changes": changed_keys}
    )

    return website

async def archive_project_website_async(
    db: AsyncSession,
    website: Website,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Website:
    website.archived = True
    website.status = "archived"
    website.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(website)

    await log_audit_event_async(
        db,
        action="website.archived",
        user_id=actor_id,
        organization_id=website.organization_id,
        target_resource=f"website:{website.id}",
        ip_address=ip_address,
        user_agent=user_agent,
        details={"website_id": website.id, "project_id": website.project_id, "domain": website.normalized_domain}
    )
    await create_org_audit_event_async(
        db,
        org_id=website.organization_id,
        action="website.archived",
        actor_id=actor_id,
        details={"website_id": website.id, "project_id": website.project_id, "domain": website.normalized_domain}
    )
    return website

async def restore_project_website_async(
    db: AsyncSession,
    website: Website,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Website:
    website.archived = False
    website.status = "active"
    website.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(website)

    await log_audit_event_async(
        db,
        action="website.restored",
        user_id=actor_id,
        organization_id=website.organization_id,
        target_resource=f"website:{website.id}",
        ip_address=ip_address,
        user_agent=user_agent,
        details={"website_id": website.id, "project_id": website.project_id, "domain": website.normalized_domain}
    )
    await create_org_audit_event_async(
        db,
        org_id=website.organization_id,
        action="website.restored",
        actor_id=actor_id,
        details={"website_id": website.id, "project_id": website.project_id, "domain": website.normalized_domain}
    )
    return website

async def delete_project_website_async(
    db: AsyncSession,
    website: Website,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    w_id = website.id
    p_id = website.project_id
    org_id = website.organization_id
    d_name = website.normalized_domain or website.domain

    await log_audit_event_async(
        db,
        action="website.deleted",
        user_id=actor_id,
        organization_id=org_id,
        target_resource=f"website:{w_id}",
        ip_address=ip_address,
        user_agent=user_agent,
        details={"website_id": w_id, "project_id": p_id, "domain": d_name}
    )
    await create_org_audit_event_async(
        db,
        org_id=org_id,
        action="website.deleted",
        actor_id=actor_id,
        details={"website_id": w_id, "project_id": p_id, "domain": d_name}
    )

    await db.delete(website)
    await db.commit()

