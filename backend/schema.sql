-- XENO CRM PostgreSQL Schema

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20),
    total_spend DECIMAL(12,2) DEFAULT 0,
    order_count INTEGER DEFAULT 0,
    last_order_date TIMESTAMP,
    first_order_date TIMESTAMP,
    avg_order_value DECIMAL(10,2) DEFAULT 0,
    tags JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    order_number VARCHAR(50),
    amount DECIMAL(12,2) NOT NULL,
    items JSONB NOT NULL DEFAULT '[]',
    channel VARCHAR(50),  -- online, in-store, app
    status VARCHAR(20) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT NOW()
);

-- AI-generated or manual segments
CREATE TABLE IF NOT EXISTS segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    rules JSONB NOT NULL,          -- structured filter rules
    natural_language_query TEXT,    -- the original NL query that created this
    customer_count INTEGER DEFAULT 0,
    is_ai_generated BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Segment membership (materialized)
CREATE TABLE IF NOT EXISTS segment_members (
    segment_id UUID REFERENCES segments(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
    PRIMARY KEY (segment_id, customer_id)
);

-- Campaigns
CREATE TABLE IF NOT EXISTS campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    segment_id UUID REFERENCES segments(id) ON DELETE SET NULL,
    message_template TEXT NOT NULL,
    channel VARCHAR(20) NOT NULL,  -- whatsapp, sms, email, rcs
    status VARCHAR(20) DEFAULT 'draft',  -- draft, sending, sent, completed
    total_recipients INTEGER DEFAULT 0,
    sent_count INTEGER DEFAULT 0,
    delivered_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    opened_count INTEGER DEFAULT 0,
    read_count INTEGER DEFAULT 0,
    clicked_count INTEGER DEFAULT 0,
    converted_count INTEGER DEFAULT 0,
    scheduled_at TIMESTAMP,
    sent_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Individual communications
CREATE TABLE IF NOT EXISTS communications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    channel VARCHAR(20) NOT NULL,
    personalised_message TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'queued',  -- queued, sent, delivered, failed, opened, read, clicked
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    failed_at TIMESTAMP,
    opened_at TIMESTAMP,
    read_at TIMESTAMP,
    clicked_at TIMESTAMP,
    converted_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- AI chat history for the agent interface
CREATE TABLE IF NOT EXISTS ai_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    messages JSONB NOT NULL DEFAULT '[]',
    context JSONB,  -- current segment, campaign in progress, etc.
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_customers_total_spend ON customers(total_spend);
CREATE INDEX IF NOT EXISTS idx_customers_last_order ON customers(last_order_date);
CREATE INDEX IF NOT EXISTS idx_communications_campaign ON communications(campaign_id);
CREATE INDEX IF NOT EXISTS idx_communications_status ON communications(status);
CREATE INDEX IF NOT EXISTS idx_segment_members_segment ON segment_members(segment_id);
