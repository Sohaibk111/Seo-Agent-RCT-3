from datetime import datetime
import csv
import io
import json
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_

from backend.database.models import AuditLog
from backend.logging_config import logger


async def log_audit_event_async(
    db: AsyncSession,
    action: str,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    target_resource: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> AuditLog:
    """
    Log an audit event to the database and standard application logger.
    """
    details_dict = details or {}
    audit_entry = AuditLog(
        user_id=user_id,
        organization_id=organization_id,
        action=action,
        target_resource=target_resource,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details_dict
    )
    db.add(audit_entry)
    try:
        await db.commit()
        await db.refresh(audit_entry)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to save audit log to DB: {e}")

    # Log to application structured logs
    logger.info(
        f"[AUDIT] action={action} user_id={user_id} org_id={organization_id} "
        f"target={target_resource} ip={ip_address} details={details_dict}"
    )

    return audit_entry


async def query_audit_logs_async(
    db: AsyncSession,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    action: Optional[str] = None,
    target_resource: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 50
) -> Tuple[List[AuditLog], int]:
    """
    Query audit logs with filtering, date range, search, and pagination.
    """
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))

    filters = []

    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)

    if organization_id is not None:
        filters.append(AuditLog.organization_id == organization_id)

    if action is not None:
        filters.append(AuditLog.action.ilike(f"%{action}%"))

    if target_resource is not None:
        filters.append(AuditLog.target_resource.ilike(f"%{target_resource}%"))

    if start_date is not None:
        filters.append(AuditLog.created_at >= start_date)

    if end_date is not None:
        filters.append(AuditLog.created_at <= end_date)

    if search:
        search_pattern = f"%{search}%"
        filters.append(
            or_(
                AuditLog.action.ilike(search_pattern),
                AuditLog.target_resource.ilike(search_pattern),
                AuditLog.ip_address.ilike(search_pattern),
                AuditLog.user_agent.ilike(search_pattern)
            )
        )

    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    # Calculate total count
    count_res = await db.execute(count_stmt)
    total = count_res.scalar() or 0

    # Paginate and order by newest first
    offset = (page - 1) * size
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(size)

    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return items, total


async def export_audit_logs_async(
    db: AsyncSession,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    action: Optional[str] = None,
    target_resource: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
    export_format: str = "csv"
) -> str:
    """
    Export audit logs in CSV or JSON format.
    """
    # Fetch all matching audit records without pagination (up to a max cap like 5000)
    items, _ = await query_audit_logs_async(
        db=db,
        user_id=user_id,
        organization_id=organization_id,
        action=action,
        target_resource=target_resource,
        start_date=start_date,
        end_date=end_date,
        search=search,
        page=1,
        size=5000
    )

    if export_format.lower() == "json":
        json_data = [
            {
                "id": item.id,
                "user_id": item.user_id,
                "organization_id": item.organization_id,
                "action": item.action,
                "target_resource": item.target_resource,
                "ip_address": item.ip_address,
                "user_agent": item.user_agent,
                "details": item.details,
                "created_at": item.created_at.isoformat() if item.created_at else None
            }
            for item in items
        ]
        return json.dumps(json_data, indent=2)

    # CSV Export
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Timestamp", "Action", "User ID", "Organization ID",
        "Target Resource", "IP Address", "User Agent", "Details"
    ])

    for item in items:
        writer.writerow([
            item.id,
            item.created_at.isoformat() if item.created_at else "",
            item.action,
            item.user_id or "",
            item.organization_id or "",
            item.target_resource or "",
            item.ip_address or "",
            item.user_agent or "",
            json.dumps(item.details) if item.details else ""
        ])

    return output.getvalue()
