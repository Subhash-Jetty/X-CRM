"""
Segmentation engine — converts structured rules to SQL queries
and materializes segment membership.
"""
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, Segment, SegmentMember


# Mapping of rule operators to SQLAlchemy filter expressions
def build_filter(field: str, operator: str, value):
    """Convert a single rule to a SQLAlchemy filter clause."""
    column = getattr(Customer, field, None)
    if column is None:
        raise ValueError(f"Unknown field: {field}")

    if operator == ">":
        return column > float(value)
    elif operator == "<":
        return column < float(value)
    elif operator == ">=":
        return column >= float(value)
    elif operator == "<=":
        return column <= float(value)
    elif operator == "==":
        return column == value
    elif operator == "!=":
        return column != value
    elif operator == "contains":
        return column.ilike(f"%{value}%")
    elif operator == "not_contains":
        return ~column.ilike(f"%{value}%")
    elif operator == "days_ago_gt":
        # "last_order_date was more than N days ago" → customers inactive for N+ days
        cutoff = datetime.utcnow() - timedelta(days=int(value))
        # Treat NULL last_order_date (never ordered) as older than cutoff
        # so they are considered inactive for this rule.
        return or_(column.is_(None), column < cutoff)
    elif operator == "days_ago_lt":
        # "last_order_date was less than N days ago" → recently active customers
        cutoff = datetime.utcnow() - timedelta(days=int(value))
        return column > cutoff
    elif operator == "is_null":
        return column.is_(None)
    elif operator == "is_not_null":
        return column.isnot(None)
    elif operator == "in":
        if isinstance(value, list):
            return column.in_(value)
        return column.in_([value])
    elif operator == "array_contains":
        # Tags are stored as a JSON array for SQLite/PostgreSQL parity.
        return column.contains([value])
    else:
        raise ValueError(f"Unknown operator: {operator}")


async def evaluate_segment_rules(db: AsyncSession, rules: list[dict]) -> list[UUID]:
    """
    Evaluate segment rules and return matching customer IDs.
    Rules are combined with AND logic.
    """
    filters = []
    for rule in rules:
        try:
            f = build_filter(rule["field"], rule["operator"], rule["value"])
            filters.append(f)
        except ValueError:
            continue  # Skip invalid rules gracefully

    if not filters:
        return []

    query = select(Customer.id).where(and_(*filters))
    result = await db.execute(query)
    return [row[0] for row in result.all()]


async def create_segment_with_members(
    db: AsyncSession,
    name: str,
    description: str | None,
    rules: list[dict],
    natural_language_query: str | None = None,
    is_ai_generated: bool = False,
) -> Segment:
    """Create a segment and materialize its members."""
    # Evaluate rules to get matching customer IDs
    customer_ids = await evaluate_segment_rules(db, rules)

    # Create segment
    segment = Segment(
        name=name,
        description=description,
        rules=rules,
        natural_language_query=natural_language_query,
        customer_count=len(customer_ids),
        is_ai_generated=is_ai_generated,
    )
    db.add(segment)
    await db.flush()

    # Add members
    for cid in customer_ids:
        member = SegmentMember(segment_id=segment.id, customer_id=cid)
        db.add(member)

    await db.flush()
    return segment


async def refresh_segment_members(db: AsyncSession, segment_id: UUID) -> int:
    """Re-evaluate segment rules and refresh membership."""
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        raise ValueError("Segment not found")

    # Clear existing members
    await db.execute(
        delete(SegmentMember).where(SegmentMember.segment_id == segment_id)
    )

    # Re-evaluate
    customer_ids = await evaluate_segment_rules(db, segment.rules)

    # Re-add members
    for cid in customer_ids:
        member = SegmentMember(segment_id=segment_id, customer_id=cid)
        db.add(member)

    segment.customer_count = len(customer_ids)
    await db.flush()
    return len(customer_ids)


async def preview_segment(db: AsyncSession, rules: list[dict], limit: int = 10):
    """Preview matching customers without creating a segment."""
    filters = []
    for rule in rules:
        try:
            f = build_filter(rule["field"], rule["operator"], rule["value"])
            filters.append(f)
        except ValueError:
            continue

    if not filters:
        return [], 0

    # Get total count
    count_query = select(func.count(Customer.id)).where(and_(*filters))
    total = (await db.execute(count_query)).scalar()

    # Get preview customers
    query = select(Customer).where(and_(*filters)).limit(limit)
    result = await db.execute(query)
    customers = result.scalars().all()

    return customers, total
