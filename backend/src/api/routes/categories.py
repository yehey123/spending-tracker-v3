"""Categories CRUD routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError

from src.db.session import get_db
from src.domain.models.category import Category
from src.domain.models.transaction import Transaction
from src.api.schemas.categories import CategoryCreate, CategoryUpdate, CategoryOut

router = APIRouter()


@router.get("/", response_model=list[CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Return all categories ordered by name ascending."""
    result = await db.execute(select(Category).order_by(Category.name.asc()))
    return result.scalars().all()


@router.post("/", response_model=CategoryOut, status_code=201)
async def create_category(body: CategoryCreate, db: AsyncSession = Depends(get_db)):
    """Create a new category. Returns 409 if name already exists (case-insensitive)."""
    cat = Category(name=body.name, color=body.color)
    db.add(cat)
    try:
        await db.commit()
        await db.refresh(cat)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Category '{body.name}' already exists.")
    return cat


@router.put("/{id}", response_model=CategoryOut)
async def update_category(id: int, body: CategoryUpdate, db: AsyncSession = Depends(get_db)):
    """Full replace of a category's fields. Returns 404 if not found."""
    result = await db.execute(select(Category).where(Category.id == id))
    cat = result.scalar_one_or_none()
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found.")
    cat.name = body.name
    cat.color = body.color
    cat.icon = body.icon
    try:
        await db.commit()
        await db.refresh(cat)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Category '{body.name}' already exists.")
    return cat


@router.delete("/{id}", status_code=204)
async def delete_category(id: int, db: AsyncSession = Depends(get_db)):
    """Delete a category, setting category_id to NULL on all linked transactions."""
    result = await db.execute(select(Category).where(Category.id == id))
    cat = result.scalar_one_or_none()
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found.")

    # Explicitly null-out transactions before deleting the category
    await db.execute(
        update(Transaction)
        .where(Transaction.category_id == id)
        .values(category_id=None)
    )
    await db.execute(delete(Category).where(Category.id == id))
    await db.commit()
