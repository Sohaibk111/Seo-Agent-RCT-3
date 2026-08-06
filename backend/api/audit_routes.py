from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
import math

from backend.database.database import get_async_db
from backend.database import schemas, crud
from backend.auth.dependencies import get_current_user
from backend.database.models import User
from backend.exceptions import ForbiddenException
from backend.services.audit_service import (
    query_audit_logs_async,
    export_audit_logs_async
)

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=schemas.AuditLogPaginated)
async def list_audit_logs(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    organization_id: Optional[int] = Query(None, description="Filter by organization ID"),
    action: Optional[str] = Query(None, description="Filter by action name or pattern"),
    target_resource: Optional[str] = Query(None, description="Filter by target resource"),
    start_date: Optional[datetime] = Query(None, description="Filter logs on or after start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Filter logs on or before end date (ISO format)"),
    search: Optional[str] = Query(None, description="Search term for action, resource, IP, user-agent"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=500, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    List and filter system & organization audit logs with search, date range filtering, and pagination.
    """
    # Scope enforcement:
    if organization_id:
        membership = await crud.get_membership_async(db, org_id=organization_id, user_id=current_user.id)
        if not membership:
            raise ForbiddenException("You are not a member of this organization")
    elif user_id and user_id != current_user.id:
        # Normal users can only inspect their own user_id logs unless org scoped or admin
        if not current_user.is_superuser:
            user_id = current_user.id
    elif not user_id and not organization_id and not current_user.is_superuser:
        # Default to current user's logs
        user_id = current_user.id

    items, total = await query_audit_logs_async(
        db=db,
        user_id=user_id,
        organization_id=organization_id,
        action=action,
        target_resource=target_resource,
        start_date=start_date,
        end_date=end_date,
        search=search,
        page=page,
        size=size
    )

    total_pages = math.ceil(total / size) if size > 0 else 0

    return schemas.AuditLogPaginated(
        items=[schemas.AuditLogOut.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
        total_pages=total_pages
    )


@router.get("/export")
async def export_audit_logs(
    user_id: Optional[int] = Query(None),
    organization_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    target_resource: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),
    format: str = Query("csv", pattern="^(csv|json)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Export audit logs matching filter criteria as downloadable CSV or JSON file.
    """
    if organization_id:
        membership = await crud.get_membership_async(db, org_id=organization_id, user_id=current_user.id)
        if not membership:
            raise ForbiddenException("You are not a member of this organization")
    elif user_id and user_id != current_user.id:
        if not current_user.is_superuser:
            user_id = current_user.id
    elif not user_id and not organization_id and not current_user.is_superuser:
        user_id = current_user.id

    exported_content = await export_audit_logs_async(
        db=db,
        user_id=user_id,
        organization_id=organization_id,
        action=action,
        target_resource=target_resource,
        start_date=start_date,
        end_date=end_date,
        search=search,
        export_format=format
    )

    if format.lower() == "json":
        return Response(
            content=exported_content,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="audit_logs.json"'}
        )

    return Response(
        content=exported_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit_logs.csv"'}
    )
