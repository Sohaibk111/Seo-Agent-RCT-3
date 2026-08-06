import base64
from typing import TypeVar, List, Generic, Optional, Any, Tuple
from sqlalchemy.orm import Query
from sqlalchemy.sql import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")

class PaginatedParams:
    """Helper for validating and sanitizing offset and limit pagination parameters."""
    def __init__(self, skip: int = 0, limit: int = 50, max_limit: int = 100):
        self.skip = max(0, skip)
        self.limit = max(1, min(limit, max_limit))

def encode_cursor(val: Any) -> str:
    """Encodes a cursor value to a URL-safe base64 string."""
    return base64.urlsafe_b64encode(str(val).encode('utf-8')).decode('utf-8')

def decode_cursor(cursor_str: str) -> str:
    """Decodes a URL-safe base64 string cursor value."""
    try:
        return base64.urlsafe_b64decode(cursor_str.encode('utf-8')).decode('utf-8')
    except Exception:
        raise ValueError("Invalid cursor format")

def paginate(query: Query, skip: int = 0, limit: int = 50, max_limit: int = 100) -> List[Any]:
    """Applies standardized bounds checking and pagination to a synchronous SQLAlchemy query."""
    params = PaginatedParams(skip=skip, limit=limit, max_limit=max_limit)
    return query.offset(params.skip).limit(params.limit).all()

def get_paginated_response(query: Query, skip: int = 0, limit: int = 50, max_limit: int = 100) -> dict:
    """Returns items along with total count metadata for synchronous API responses."""
    params = PaginatedParams(skip=skip, limit=limit, max_limit=max_limit)
    total = query.count()
    items = query.offset(params.skip).limit(params.limit).all()
    pages = (total + params.limit - 1) // params.limit if params.limit > 0 else 1
    return {
        "items": items,
        "total": total,
        "skip": params.skip,
        "limit": params.limit,
        "pages": pages
    }

async def async_paginate(db: AsyncSession, stmt: Select, skip: int = 0, limit: int = 50, max_limit: int = 100) -> List[Any]:
    """Applies standardized bounds checking and pagination asynchronously to a SQLAlchemy Select statement."""
    params = PaginatedParams(skip=skip, limit=limit, max_limit=max_limit)
    paginated_stmt = stmt.offset(params.skip).limit(params.limit)
    result = await db.execute(paginated_stmt)
    return list(result.scalars().all())

async def get_async_paginated_response(db: AsyncSession, stmt: Select, skip: int = 0, limit: int = 50, max_limit: int = 100) -> dict:
    """Returns items along with total count metadata asynchronously for API responses."""
    params = PaginatedParams(skip=skip, limit=limit, max_limit=max_limit)
    
    # Count total records
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one_or_none() or 0

    items = await async_paginate(db, stmt, skip=skip, limit=limit, max_limit=max_limit)
    pages = (total + params.limit - 1) // params.limit if params.limit > 0 else 1
    
    return {
        "items": items,
        "total": total,
        "skip": params.skip,
        "limit": params.limit,
        "pages": pages
    }

def cursor_paginate(
    query: Query,
    column,
    cursor: Optional[str] = None,
    limit: int = 50,
    max_limit: int = 100,
    order: str = "desc"
) -> Tuple[List[Any], Optional[str], bool]:
    """
    Synchronous keyset/cursor-based pagination to eliminate expensive OFFSET queries.
    Returns (items, next_cursor, has_more).
    """
    eff_limit = max(1, min(limit, max_limit))
    
    if cursor:
        decoded_val = decode_cursor(cursor)
        # Attempt integer conversion if appropriate
        try:
            val = int(decoded_val)
        except ValueError:
            val = decoded_val

        if order.lower() == "asc":
            query = query.filter(column > val)
        else:
            query = query.filter(column < val)

    if order.lower() == "asc":
        query = query.order_by(column.asc())
    else:
        query = query.order_by(column.desc())

    # Fetch limit + 1 to determine if there are remaining pages
    items = query.limit(eff_limit + 1).all()
    has_more = len(items) > eff_limit
    
    if has_more:
        items = items[:eff_limit]
        last_item = items[-1]
        # Get attribute value from model instance or tuple
        last_val = getattr(last_item, column.name if hasattr(column, "name") else "id")
        next_cursor = encode_cursor(last_val)
    else:
        next_cursor = None

    return items, next_cursor, has_more

async def async_cursor_paginate(
    db: AsyncSession,
    stmt: Select,
    column,
    cursor: Optional[str] = None,
    limit: int = 50,
    max_limit: int = 100,
    order: str = "desc"
) -> Tuple[List[Any], Optional[str], bool]:
    """
    Asynchronous keyset/cursor-based pagination to eliminate expensive OFFSET queries.
    Returns (items, next_cursor, has_more).
    """
    eff_limit = max(1, min(limit, max_limit))
    
    if cursor:
        decoded_val = decode_cursor(cursor)
        try:
            val = int(decoded_val)
        except ValueError:
            val = decoded_val

        if order.lower() == "asc":
            stmt = stmt.where(column > val)
        else:
            stmt = stmt.where(column < val)

    if order.lower() == "asc":
        stmt = stmt.order_by(column.asc())
    else:
        stmt = stmt.order_by(column.desc())

    stmt = stmt.limit(eff_limit + 1)
    result = await db.execute(stmt)
    items = list(result.scalars().all())
    
    has_more = len(items) > eff_limit
    if has_more:
        items = items[:eff_limit]
        last_item = items[-1]
        col_name = column.key if hasattr(column, "key") else getattr(column, "name", "id")
        last_val = getattr(last_item, col_name)
        next_cursor = encode_cursor(last_val)
    else:
        next_cursor = None

    return items, next_cursor, has_more

