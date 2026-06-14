"""
Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator


# ──────────────────────────────────────────────
# Customer Schemas
# ──────────────────────────────────────────────

class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class CustomerResponse(BaseModel):
    id: UUID
    name: Optional[str] = "Unknown"
    email: Optional[str] = None
    phone: Optional[str] = None
    total_spend: Optional[float] = 0.0
    order_count: Optional[int] = 0
    last_order_date: Optional[datetime] = None
    first_order_date: Optional[datetime] = None
    avg_order_value: Optional[float] = 0.0
    tags: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None

    @field_validator("tags", mode="before")
    @classmethod
    def handle_null_tags(cls, v):
        return v if v is not None else []

    @field_validator("name", mode="before")
    @classmethod
    def handle_null_name(cls, v):
        return v if v is not None else "Unknown"

    model_config = {"from_attributes": True}


class CustomerBulkIngest(BaseModel):
    customers: list[CustomerCreate]


# ──────────────────────────────────────────────
# Order Schemas
# ──────────────────────────────────────────────

class OrderItem(BaseModel):
    name: str
    quantity: int = 1
    price: float


class OrderCreate(BaseModel):
    customer_id: Optional[UUID] = None
    customer_email: Optional[str] = None  # Lookup by email if no ID
    order_number: Optional[str] = None
    amount: float
    items: list[OrderItem] = Field(default_factory=list)
    channel: Optional[str] = None
    status: str = "completed"
    created_at: Optional[datetime] = None


class OrderResponse(BaseModel):
    id: UUID
    customer_id: UUID
    order_number: Optional[str] = None
    amount: Optional[float] = 0.0
    items: list = Field(default_factory=list)
    channel: Optional[str] = None
    status: Optional[str] = "completed"
    created_at: Optional[datetime] = None

    @field_validator("items", mode="before")
    @classmethod
    def handle_null_items(cls, v):
        return v if v is not None else []

    model_config = {"from_attributes": True}


class OrderBulkIngest(BaseModel):
    orders: list[OrderCreate]


# ──────────────────────────────────────────────
# Segment Schemas
# ──────────────────────────────────────────────

class SegmentRule(BaseModel):
    """A single filter rule for segmentation."""
    field: str  # e.g., "total_spend", "order_count", "last_order_date", "tags"
    operator: str  # e.g., ">", "<", ">=", "<=", "==", "!=", "contains", "not_contains", "days_ago_gt", "days_ago_lt"
    value: str | int | float | list


class SegmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rules: list[SegmentRule]
    natural_language_query: Optional[str] = None
    is_ai_generated: bool = False


class SegmentResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    rules: list = Field(default_factory=list)
    natural_language_query: Optional[str] = None
    customer_count: Optional[int] = 0
    is_ai_generated: Optional[bool] = False
    created_at: Optional[datetime] = None

    @field_validator("rules", mode="before")
    @classmethod
    def handle_null_rules(cls, v):
        return v if v is not None else []

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Campaign Schemas
# ──────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str
    segment_id: UUID
    message_template: str
    channel: str = "whatsapp"  # whatsapp, sms, email, rcs
    scheduled_at: Optional[datetime] = None


class CampaignResponse(BaseModel):
    id: UUID
    name: str
    segment_id: Optional[UUID]
    message_template: str
    channel: str
    status: str
    total_recipients: int
    sent_count: int
    delivered_count: int
    failed_count: int
    opened_count: int
    read_count: int
    clicked_count: int
    converted_count: int
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class CampaignStats(BaseModel):
    total_recipients: int
    sent: int
    delivered: int
    failed: int
    opened: int
    read: int
    clicked: int
    converted: int
    delivery_rate: float
    open_rate: float
    click_rate: float
    conversion_rate: float


# ──────────────────────────────────────────────
# Communication / Receipt Schemas
# ──────────────────────────────────────────────

class CommunicationResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    customer_id: Optional[UUID]
    channel: str
    personalised_message: str
    status: str
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    failed_at: Optional[datetime]
    opened_at: Optional[datetime]
    read_at: Optional[datetime]
    clicked_at: Optional[datetime]
    converted_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class DeliveryReceipt(BaseModel):
    """Callback from the channel service."""
    communication_id: UUID
    status: str  # delivered, failed, opened, read, clicked, converted
    timestamp: datetime
    error_message: Optional[str] = None


class DeliveryReceiptBatch(BaseModel):
    receipts: list[DeliveryReceipt]


# ──────────────────────────────────────────────
# AI Chat Schemas
# ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # user, assistant
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[UUID] = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: UUID
    actions_taken: list[dict] = Field(default_factory=list)  # e.g., [{"type": "segment_created", "id": "..."}]


class NLSegmentRequest(BaseModel):
    query: str  # "customers who spent more than 5000 in the last month"


# ──────────────────────────────────────────────
# General
# ──────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    total_pages: int


class MessageResponse(BaseModel):
    message: str
    count: Optional[int] = None
