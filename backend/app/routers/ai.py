"""
AI Agent API routes — chat, segment suggestions, message drafting.
"""
import json
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AIConversation, Customer, Segment, Campaign
from app.schemas import ChatRequest, ChatResponse, NLSegmentRequest
from app.services.ai_agent import (
    chat_with_ai,
    generate_message_draft,
    generate_segment_suggestions,
)
from app.services.segmentation import (
    create_segment_with_members,
    preview_segment,
    evaluate_segment_rules,
)
from app.services.campaign_engine import send_campaign, get_campaign_stats

router = APIRouter()


async def get_db_context(db: AsyncSession) -> dict:
    """Build context about the database for the AI agent."""
    # Get customer stats
    result = await db.execute(
        select(
            func.count(Customer.id).label("total_customers"),
            func.coalesce(func.avg(Customer.total_spend), 0).label("avg_spend"),
            func.coalesce(func.max(Customer.total_spend), 0).label("max_spend"),
            func.coalesce(func.avg(Customer.order_count), 0).label("avg_orders"),
        )
    )
    row = result.one()

    # Get segment count
    seg_count = (await db.execute(select(func.count(Segment.id)))).scalar()

    # Get campaign count
    camp_count = (await db.execute(select(func.count(Campaign.id)))).scalar()

    return {
        "total_customers": row.total_customers,
        "avg_customer_spend": round(float(row.avg_spend), 2),
        "max_customer_spend": round(float(row.max_spend), 2),
        "avg_orders_per_customer": round(float(row.avg_orders), 1),
        "total_segments": seg_count,
        "total_campaigns": camp_count,
    }


async def execute_tool_call(db: AsyncSession, tool_name: str, arguments: dict) -> dict:
    """Execute a tool call requested by the AI agent."""
    if tool_name == "query_customers":
        filters = arguments.get("filters", [])
        customers, total = await preview_segment(db, filters, limit=5)
        return {
            "total_matching": total,
            "sample_customers": [
                {"name": c.name, "email": c.email, "total_spend": c.total_spend,
                 "order_count": c.order_count, "last_order_date": str(c.last_order_date) if c.last_order_date else None}
                for c in customers
            ],
        }

    elif tool_name == "create_segment":
        segment = await create_segment_with_members(
            db=db,
            name=arguments["name"],
            description=arguments.get("description", ""),
            rules=arguments["rules"],
            natural_language_query=arguments.get("description", ""),
            is_ai_generated=True,
        )
        return {
            "segment_id": str(segment.id),
            "name": segment.name,
            "customer_count": segment.customer_count,
        }

    elif tool_name == "create_campaign":
        campaign = Campaign(
            name=arguments["name"],
            segment_id=arguments["segment_id"],
            message_template=arguments["message_template"],
            channel=arguments.get("channel", "whatsapp"),
        )
        db.add(campaign)
        await db.flush()
        return {
            "campaign_id": str(campaign.id),
            "name": campaign.name,
            "status": "draft",
        }

    elif tool_name == "draft_message":
        message = await generate_message_draft(
            segment_description=arguments["segment_description"],
            channel=arguments.get("channel", "whatsapp"),
            tone=arguments.get("tone", "friendly"),
            offer=arguments.get("offer"),
        )
        return {"drafted_message": message}

    elif tool_name == "get_campaign_stats":
        try:
            stats = await get_campaign_stats(db, arguments["campaign_id"])
            return stats
        except ValueError:
            return {"error": "Campaign not found"}

    elif tool_name == "send_campaign":
        try:
            count = await send_campaign(db, arguments["campaign_id"])
            return {
                "status": "sent",
                "recipients": count,
                "message": f"Campaign sent to {count} recipients. Delivery receipts will arrive shortly.",
            }
        except ValueError as e:
            return {"error": str(e)}

    elif tool_name == "get_insights":
        context = await get_db_context(db)
        suggestions = await generate_segment_suggestions(context)
        return {"stats": context, "suggestions": suggestions}

    return {"error": f"Unknown tool: {tool_name}"}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Main AI chat endpoint. Handles natural language interactions."""
    # Load or create conversation
    conversation_id = request.conversation_id
    history = []

    if conversation_id:
        result = await db.execute(
            select(AIConversation).where(AIConversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            history = conv.messages or []

    # Get database context for the AI
    db_context = await get_db_context(db)

    # Get AI response
    reply, tool_calls = await chat_with_ai(request.message, history, db_context)

    # Execute any tool calls
    actions_taken = []
    tool_results = []
    for tc in tool_calls:
        result = await execute_tool_call(db, tc["name"], tc["arguments"])
        actions_taken.append({
            "type": tc["name"],
            "arguments": tc["arguments"],
            "result": result,
        })
        tool_results.append(result)

    # If tools were called, get a follow-up response with tool results
    if tool_calls and tool_results:
        followup_messages = history + [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": reply or "Let me look into that..."},
            {"role": "user", "content": f"Tool results: {json.dumps(tool_results, default=str)}. Please summarize these results naturally for the marketer."},
        ]
        reply, _ = await chat_with_ai(
            f"Based on the tool results above, provide a clear, actionable response to the marketer.",
            followup_messages,
            db_context,
        )

    # Save conversation
    if not conversation_id:
        conversation_id = uuid4()

    # Update history
    history.append({"role": "user", "content": request.message})
    history.append({"role": "assistant", "content": reply})

    # Upsert conversation
    result = await db.execute(
        select(AIConversation).where(AIConversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv:
        conv.messages = history
    else:
        conv = AIConversation(id=conversation_id, messages=history, context=db_context)
        db.add(conv)

    await db.flush()

    return ChatResponse(
        reply=reply,
        conversation_id=conversation_id,
        actions_taken=actions_taken,
    )


@router.post("/suggest-segments")
async def suggest_segments(db: AsyncSession = Depends(get_db)):
    """AI-generated segment suggestions based on current data."""
    context = await get_db_context(db)
    suggestions = await generate_segment_suggestions(context)
    return {"suggestions": suggestions}


@router.post("/draft-message")
async def draft_message(request: NLSegmentRequest, db: AsyncSession = Depends(get_db)):
    """Draft a marketing message from a natural language description."""
    message = await generate_message_draft(
        segment_description=request.query,
        channel="whatsapp",
        tone="friendly",
    )
    return {"message": message}
