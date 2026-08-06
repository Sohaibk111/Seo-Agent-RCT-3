from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.database import get_async_db
from backend.database import crud, schemas
from backend.auth.dependencies import get_current_user
from backend.database.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=dict)
async def register(user_in: schemas.UserCreate, db: AsyncSession = Depends(get_async_db)):
    existing = await crud.get_user_by_email_async(db, email=user_in.email)
    if not existing:
        user = await crud.create_user_async(db, email=user_in.email, username=user_in.username)
    else:
        user = existing
    
    token = f"token_user_{user.id}"
    return {
        "id": user.id,
        "email": user.email,
        "access_token": token,
        "token_type": "bearer"
    }

@router.post("/login", response_model=dict)
async def login(user_in: schemas.UserCreate, db: AsyncSession = Depends(get_async_db)):
    user = await crud.get_user_by_email_async(db, email=user_in.email)
    if not user:
        user = await crud.create_user_async(db, email=user_in.email, username=user_in.username)
    
    token = f"token_user_{user.id}"
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "user_id": user.id
    }

@router.get("/me", response_model=schemas.UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
