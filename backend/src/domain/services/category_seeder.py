"""Seed default system categories on startup (idempotent via slug unique constraint)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.category import Category

DEFAULTS = [
    ("food",          "Food & Dining",     "#f97316", [
        ("food_delivery",  "Food Delivery",    "#fb923c"),
        ("fast_food",      "Fast Food",        "#fbbf24"),
        ("coffee",         "Coffee & Drinks",  "#92400e"),
        ("groceries",      "Groceries",        "#84cc16"),
    ]),
    ("transport",     "Transport",         "#3b82f6", [
        ("ride_hailing",   "Ride Hailing",     "#60a5fa"),
        ("fuel",           "Fuel",             "#1d4ed8"),
        ("parking",        "Parking",          "#93c5fd"),
    ]),
    ("entertainment", "Entertainment",     "#a855f7", [
        ("streaming",      "Streaming",        "#c084fc"),
        ("events",         "Events",           "#7c3aed"),
    ]),
    ("bills",         "Bills & Utilities", "#14b8a6", [
        ("internet",       "Internet",         "#2dd4bf"),
        ("mobile",         "Mobile",           "#0d9488"),
        ("electricity",    "Electricity",      "#f59e0b"),
    ]),
    ("income",        "Income",            "#22c55e", [
        ("salary",         "Salary",           "#16a34a"),
        ("freelance",      "Freelance",        "#4ade80"),
    ]),
    ("shopping",      "Shopping",          "#ec4899", [
        ("online",         "Online Shopping",  "#f472b6"),
        ("clothing",       "Clothing",         "#db2777"),
    ]),
    ("health",        "Health",            "#06b6d4", [
        ("pharmacy",       "Pharmacy",         "#22d3ee"),
        ("medical",        "Medical",          "#0891b2"),
    ]),
]


async def seed_default_categories(db: AsyncSession) -> None:
    """Insert default categories if they don't exist (idempotent via slug)."""
    for slug, name, color, children in DEFAULTS:
        result = await db.execute(
            insert(Category)
            .values(slug=slug, name=name, color=color, is_system=True)
            .on_conflict_do_nothing(index_elements=["slug"])
            .returning(Category.id)
        )
        parent_id_row = result.first()
        if parent_id_row is None:
            existing = await db.execute(
                select(Category.id).where(Category.slug == slug)
            )
            parent_id = existing.scalar()
        else:
            parent_id = parent_id_row[0]

        for child_slug, child_name, child_color in children:
            await db.execute(
                insert(Category)
                .values(
                    slug=child_slug, name=child_name, color=child_color,
                    parent_id=parent_id, is_system=True
                )
                .on_conflict_do_nothing(index_elements=["slug"])
            )

    await db.commit()


if __name__ == "__main__":
    import asyncio
    from src.db.session import AsyncSessionLocal

    async def _run() -> None:
        async with AsyncSessionLocal() as db:
            await seed_default_categories(db)

    asyncio.run(_run())
