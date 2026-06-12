"""
SQLAlchemy models for the XENO CRM database.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, Index, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True)
    phone = Column(String(20))
    total_spend = Column(Float, default=0)
    order_count = Column(Integer, default=0)
    last_order_date = Column(DateTime)
    first_order_date = Column(DateTime)
    avg_order_value = Column(Float, default=0)
    tags = Column(ARRAY(String), default=[])
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    orders = relationship("Order", back_populates="customer", lazy="selectin")
    communications = relationship("Communication", back_populates="customer", lazy="selectin")

    __table_args__ = (
        Index("idx_customers_total_spend", "total_spend"),
        Index("idx_customers_last_order", "last_order_date"),
    )


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    order_number = Column(String(50))
    amount = Column(Float, nullable=False)
    items = Column(JSONB, default=[])
    channel = Column(String(50))  # online, in-store, app
    status = Column(String(20), default="completed")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="orders")

    __table_args__ = (
        Index("idx_orders_customer_id", "customer_id"),
        Index("idx_orders_created_at", "created_at"),
    )


class Segment(Base):
    __tablename__ = "segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    rules = Column(JSONB, nullable=False)
    natural_language_query = Column(Text)
    customer_count = Column(Integer, default=0)
    is_ai_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    members = relationship("SegmentMember", back_populates="segment", lazy="selectin", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="segment", lazy="selectin")


class SegmentMember(Base):
    __tablename__ = "segment_members"

    segment_id = Column(UUID(as_uuid=True), ForeignKey("segments.id", ondelete="CASCADE"), primary_key=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True)

    # Relationships
    segment = relationship("Segment", back_populates="members")
    customer = relationship("Customer")

    __table_args__ = (
        Index("idx_segment_members_segment", "segment_id"),
    )


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    segment_id = Column(UUID(as_uuid=True), ForeignKey("segments.id"))
    message_template = Column(Text, nullable=False)
    channel = Column(String(20), nullable=False)  # whatsapp, sms, email, rcs
    status = Column(String(20), default="draft")  # draft, sending, sent, completed
    total_recipients = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    delivered_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    opened_count = Column(Integer, default=0)
    read_count = Column(Integer, default=0)
    clicked_count = Column(Integer, default=0)
    converted_count = Column(Integer, default=0)
    scheduled_at = Column(DateTime)
    sent_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    segment = relationship("Segment", back_populates="campaigns")
    communications = relationship("Communication", back_populates="campaign", lazy="selectin", cascade="all, delete-orphan")


class Communication(Base):
    __tablename__ = "communications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"))
    channel = Column(String(20), nullable=False)
    personalised_message = Column(Text, nullable=False)
    status = Column(String(20), default="queued")  # queued, sent, delivered, failed, opened, read, clicked
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    failed_at = Column(DateTime)
    opened_at = Column(DateTime)
    read_at = Column(DateTime)
    clicked_at = Column(DateTime)
    converted_at = Column(DateTime)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    campaign = relationship("Campaign", back_populates="communications")
    customer = relationship("Customer", back_populates="communications")

    __table_args__ = (
        Index("idx_communications_campaign", "campaign_id"),
        Index("idx_communications_status", "status"),
    )


class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    messages = Column(JSONB, default=[])
    context = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
