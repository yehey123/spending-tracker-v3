"""Categories CRUD routes with two-level hierarchy support."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas.categories import CategoryCreate, CategoryOut, CategoryUpdate
from src.db.session import get_db
from src.domain.models.category import Category
from src.domain.models.transaction import Transaction

router = APIRouter()


def _to_tree(cat: Category) -> dict:
    return {
        "id": cat.id,
        "name": cat.name,
        "color": cat.color,
        "icon": cat.icon,
        "slug": cat.slug,
        "is_system": cat.is_system,
        "parent_id": cat.parent_id,
        "children": [_to_tree(c) for c in (cat.children or [])],
    }


@router.get("", response_model=list[CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Return all top-level categories with nested children."""
    result = await db.execute(
        select(Category)
        .where(Category.parent_id.is_(None))
        .options(selectinload(Category.children).selectinload(Category.children))
        .order_by(Category.name.asc())
    )
    parents = result.scalars().unique().all()
    return [_to_tree(p) for p in parents]


@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(body: CategoryCreate, db: AsyncSession = Depends(get_db)):
    """Create a category. parent_id enforces max 2-level depth."""
    if body.parent_id is not None:
        parent = await db.get(Category, body.parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="Parent category not found.")
        if parent.parent_id is not None:
            raise HTTPException(
                status_code=422, detail="Subcategories cannot have children (max 2 levels)."
            )

    cat = Category(
        name=body.name,
        color=body.color or "#6B7280",
        icon=body.icon,
        parent_id=body.parent_id,
    )
    db.add(cat)
    try:
        await db.commit()
        await db.refresh(cat)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Category '{body.name}' already exists.")

    result = await db.execute(
        select(Category).options(selectinload(Category.children)).where(Category.id == cat.id)
    )
    return _to_tree(result.scalar_one())


@router.put("/{id}", response_model=CategoryOut)
async def update_category(id: int, body: CategoryUpdate, db: AsyncSession = Depends(get_db)):
    """Full replace of category fields. Validates depth if parent_id changes."""
    result = await db.execute(
        select(Category).options(selectinload(Category.children)).where(Category.id == id)
    )
    cat = result.scalar_one_or_none()
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found.")

    if body.parent_id is not None and body.parent_id != cat.parent_id:
        parent = await db.get(Category, body.parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="Parent category not found.")
        if parent.parent_id is not None:
            raise HTTPException(
                status_code=422, detail="Subcategories cannot have children (max 2 levels)."
            )

    cat.name = body.name
    cat.color = body.color or "#6B7280"
    cat.icon = body.icon
    cat.parent_id = body.parent_id
    try:
        await db.commit()
        await db.refresh(cat)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Category '{body.name}' already exists.")

    result2 = await db.execute(
        select(Category).options(selectinload(Category.children)).where(Category.id == id)
    )
    return _to_tree(result2.scalar_one())


@router.delete("/{id}", status_code=204)
async def delete_category(id: int, db: AsyncSession = Depends(get_db)):
    """Delete a category. Fails if it has children; nullifies linked transactions."""
    cat = await db.get(Category, id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found.")

    children_count = await db.execute(
        select(func.count()).where(Category.parent_id == id)
    )
    if children_count.scalar() > 0:
        raise HTTPException(
            status_code=422, detail="Delete or reassign subcategories first."
        )

    await db.execute(
        update(Transaction).where(Transaction.category_id == id).values(category_id=None)
    )
    await db.execute(delete(Category).where(Category.id == id))
    await db.commit()
