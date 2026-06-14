"""
Customer ingestion and data management service.
"""
from datetime import datetime
from uuid import UUID
from sqlalchemy import select, func, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models import Customer, Order


# --- Datetime / UUID fields that need native Python types for asyncpg ---
_CUSTOMER_DATETIME_FIELDS = {"created_at", "updated_at", "last_order_date", "first_order_date"}
_CUSTOMER_UUID_FIELDS = {"id"}

_ORDER_DATETIME_FIELDS = {"created_at"}
_ORDER_UUID_FIELDS = {"id", "customer_id"}
_UPSERT_CHUNK_SIZE = 500


def _model_column_names(model) -> set[str]:
    return {col.name for col in model.__table__.columns}


def _normalise_customer_record(record: dict) -> dict:
    """Map rich demo/export customer rows onto the CRM customer schema."""
    normalised = dict(record)

    if not normalised.get("name"):
        name_parts = [normalised.get("first_name"), normalised.get("last_name")]
        name = " ".join(part for part in name_parts if part)
        if name:
            normalised["name"] = name

    if not normalised.get("last_order_date") and normalised.get("last_active"):
        normalised["last_order_date"] = normalised["last_active"]

    allowed_columns = _model_column_names(Customer)
    return {key: value for key, value in normalised.items() if key in allowed_columns}


def _coerce_types(record: dict, datetime_fields: set, uuid_fields: set) -> dict:
    """
    Convert ISO-format datetime strings → datetime objects and
    string UUIDs → uuid.UUID objects in-place.  asyncpg requires
    native Python types; it will not auto-cast from str.
    """
    for field in datetime_fields:
        val = record.get(field)
        if isinstance(val, str):
            record[field] = datetime.fromisoformat(val)

    for field in uuid_fields:
        val = record.get(field)
        if isinstance(val, str):
            record[field] = UUID(val)

    return record


def _dialect_name(db: AsyncSession) -> str:
    bind = db.get_bind()
    return bind.dialect.name if bind is not None else ""


def _upsert_insert(model, values: list[dict], constraint_columns: list[str], db: AsyncSession):
    """Build a dialect-aware upsert for the supported local/prod databases."""
    dialect = _dialect_name(db)
    if dialect == "postgresql":
        stmt = pg_insert(model).values(values)
    elif dialect == "sqlite":
        stmt = sqlite_insert(model).values(values)
    else:
        return None

    update_dict = {
        col.name: stmt.excluded[col.name]
        for col in model.__table__.columns
        if col.name not in ["id", "created_at"]
    }
    return stmt.on_conflict_do_update(
        index_elements=constraint_columns,
        set_=update_dict,
    )


async def ingest_customers(db: AsyncSession, customers_data: list[dict]) -> int:
    """
    Bulk upsert customers using the active database dialect.
    """
    if not customers_data:
        return 0

    # Coerce str → datetime / UUID so asyncpg doesn't choke
    prepared_customers = []
    for rec in customers_data:
        normalised = _normalise_customer_record(rec)
        _coerce_types(normalised, _CUSTOMER_DATETIME_FIELDS, _CUSTOMER_UUID_FIELDS)
        prepared_customers.append(normalised)

    if _dialect_name(db) in {"postgresql", "sqlite"}:
        for i in range(0, len(prepared_customers), _UPSERT_CHUNK_SIZE):
            chunk = prepared_customers[i:i + _UPSERT_CHUNK_SIZE]
            stmt = _upsert_insert(Customer, chunk, ["email"], db)
            await db.execute(stmt)
    else:
        for record in prepared_customers:
            await db.merge(Customer(**record))

    await db.flush()
    return len(prepared_customers)


async def ingest_orders(db: AsyncSession, orders_data: list[dict]) -> int:
    """
    Bulk insert orders and update customer aggregates in batch.
    """
    if not orders_data:
        return 0

    # 1. Bulk resolve customer emails to IDs
    emails = list({o["customer_email"] for o in orders_data if o.get("customer_email")})
    email_to_id = {}
    if emails:
        stmt = select(Customer.email, Customer.id).where(Customer.email.in_(emails))
        result = await db.execute(stmt)
        for row in result.all():
            email_to_id[row.email] = row.id

    # 2. Prepare order dicts with resolved customer_ids
    valid_orders = []
    for o in orders_data:
        c_email = o.pop("customer_email", None)
        c_id = o.get("customer_id")
        if not c_id and c_email and c_email in email_to_id:
            c_id = email_to_id[c_email]
            
        if c_id:
            o["customer_id"] = c_id
            # Coerce str → datetime / UUID so asyncpg doesn't choke
            _coerce_types(o, _ORDER_DATETIME_FIELDS, _ORDER_UUID_FIELDS)
            valid_orders.append(o)
            
    if not valid_orders:
        return 0

    # 3. Bulk upsert orders by primary key. The seed data includes stable UUIDs,
    # so rerunning ingestion should refresh rows rather than duplicate them.
    stmt = _upsert_insert(Order, valid_orders, ["id"], db)
    if stmt is not None:
        await db.execute(stmt)
    else:
        await db.execute(insert(Order).values(valid_orders))
    await db.flush()

    # 4. Update aggregates in one go for ALL customers
    await _update_all_customer_aggregates(db)
    
    return len(valid_orders)


async def _update_all_customer_aggregates(db: AsyncSession):
    """Recalculate aggregates from the orders table using a single bulk UPDATE."""
    now = datetime.utcnow()

    # Build a subquery with per-customer aggregates
    stats_sub = (
        select(
            Order.customer_id.label("cid"),
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.amount), 0).label("total_spend"),
            func.min(Order.created_at).label("first_order_date"),
            func.max(Order.created_at).label("last_order_date"),
        )
        .group_by(Order.customer_id)
        .subquery("order_stats")
    )

    # Single bulk UPDATE using correlated subquery — avoids N round-trips
    await db.execute(
        update(Customer)
        .where(Customer.id == stats_sub.c.cid)
        .values(
            order_count=stats_sub.c.order_count,
            total_spend=stats_sub.c.total_spend,
            first_order_date=stats_sub.c.first_order_date,
            last_order_date=stats_sub.c.last_order_date,
            avg_order_value=func.case(
                (stats_sub.c.order_count > 0,
                 stats_sub.c.total_spend / stats_sub.c.order_count),
                else_=0,
            ),
            updated_at=now,
        )
    )
