"""
AI Agent API routes — chat, segment suggestions, message drafting.
"""
import json
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
import re
from sqlalchemy import select, func, update
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
from app.services.campaign_engine import CampaignDispatchError, send_campaign, get_campaign_stats

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


async def save_chat_turn(
    db: AsyncSession,
    conversation_id: UUID | None,
    history: list,
    db_context: dict,
    user_message: str,
    assistant_reply: str,
) -> UUID:
    """Persist one user/assistant chat turn and return the conversation id."""
    if not conversation_id:
        conversation_id = uuid4()

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": assistant_reply})

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
    return conversation_id


def wants_segment_creation(message: str) -> bool:
    """Return true when the marketer explicitly asks to create/save a segment."""
    return bool(re.search(r"\b(create|save|persist|make|build)\b", message, re.IGNORECASE)) and bool(
        re.search(r"\bsegment|audience\b", message, re.IGNORECASE)
    )


def wants_campaign_launch(message: str) -> bool:
    """Return true when the marketer asks to dispatch a campaign, not just draft it."""
    return bool(
        re.search(r"\b(send|launch|start|dispatch|go\s+live|run)\b", message, re.IGNORECASE)
    ) and bool(re.search(r"\bcamp(?:aign|iagn)\b", message, re.IGNORECASE))


def parse_inactive_segment_request(message: str) -> int | None:
    """Extract N from requests like 'inactive for the past 15 days'."""
    inactive_terms = (
        r"(?:inactive|not\s+active|no\s+(?:orders?|purchases?|activity)|"
        r"without\s+(?:orders?|purchases?|activity))"
    )
    period_words = r"(?:past|last|previous)"
    common_patterns = [
        # inactive for 15 days / inactive for the last 15 days / inactive last 15 days
        rf"{inactive_terms}.{{0,120}}?(?:for|since|over|in|during)?\s*"
        rf"(?:the\s+)?(?:{period_words}\s+)?([0-9]{{1,4}})\s+days?",
        # last 15 days inactive / 15 days without orders
        rf"(?:{period_words}\s+)?([0-9]{{1,4}})\s+days?.{{0,120}}?{inactive_terms}",
    ]
    for pattern in common_patterns:
        common_match = re.search(pattern, message, re.IGNORECASE)
        if common_match:
            return int(common_match.group(1))

    inactive_pattern = re.search(
        r"(?:inactive|not\s+active|no\s+(?:orders?|purchases?|activity)|haven['’]?t\s+(?:ordered|purchased|been\s+active))"
        r".{0,80}?(?:past|last|for|since)\s+([0-9]{1,4})\s+days?",
        message,
        re.IGNORECASE,
    )
    if inactive_pattern:
        return int(inactive_pattern.group(1))

    days_first_pattern = re.search(
        r"(?:past|last)\s+([0-9]{1,4})\s+days?.{0,80}?"
        r"(?:inactive|not\s+active|no\s+(?:orders?|purchases?|activity)|haven['’]?t\s+(?:ordered|purchased|been\s+active))",
        message,
        re.IGNORECASE,
    )
    if days_first_pattern:
        return int(days_first_pattern.group(1))

    return None


async def ensure_high_value_segment(db: AsyncSession) -> Segment:
    existing_result = await db.execute(
        select(Segment)
        .where(func.lower(Segment.name).in_(["high-value customers", "high value customers", "vip customers"]))
        .order_by(Segment.created_at.desc())
    )
    existing_segment = existing_result.scalar_one_or_none()
    if existing_segment:
        return existing_segment

    rules = [{"field": "total_spend", "operator": ">=", "value": 5000}]
    _, total = await preview_segment(db, rules, limit=1)
    if not total:
        rules = [{"field": "order_count", "operator": ">", "value": 0}]

    return await create_segment_with_members(
        db=db,
        name="High-Value Customers",
        description="Customers selected for high-value WhatsApp campaign launch",
        rules=rules,
        natural_language_query="Auto-created for campaign launch",
        is_ai_generated=True,
    )


async def launch_campaign_from_chat(db: AsyncSession, message: str) -> tuple[str, list[dict]]:
    draft_result = await db.execute(
        select(Campaign)
        .where(Campaign.status.in_(["draft", "scheduled"]))
        .order_by(Campaign.created_at.desc())
    )
    campaign = draft_result.scalar_one_or_none()

    actions_taken = []

    if not campaign:
        segment = await ensure_high_value_segment(db)
        campaign = Campaign(
            name=f"AI WhatsApp Campaign {uuid4().hex[:6].upper()}",
            segment_id=segment.id,
            message_template=(
                "Hi {{first_name}}, thanks for being one of our valued customers. "
                "Here is an exclusive BeanBox offer just for you. Visit us today to redeem it."
            ),
            channel="whatsapp",
        )
        db.add(campaign)
        await db.flush()
        actions_taken.append({
            "type": "create_campaign",
            "arguments": {
                "name": campaign.name,
                "segment_id": str(segment.id),
                "channel": campaign.channel,
            },
            "result": {
                "campaign_id": str(campaign.id),
                "name": campaign.name,
                "status": "draft",
            },
        })

    send_result = await execute_tool_call(db, "send_campaign", {"campaign_id": str(campaign.id)})
    actions_taken.append({
        "type": "send_campaign",
        "arguments": {"campaign_id": str(campaign.id)},
        "result": send_result,
    })

    if send_result.get("status") == "sent":
        reply = f'Launched "{campaign.name}" to {send_result["recipients"]} recipients.'
    else:
        reply = f'Campaign "{campaign.name}" was created, but launch failed: {send_result.get("error", "unknown error")}'

    return reply, actions_taken


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
        # Support preview mode by default. If caller passes persist=True, actually create the segment.
        persist = bool(arguments.get("persist", False))
        rules = arguments.get("rules", [])
        name = arguments.get("name")
        description = arguments.get("description", "")

        if not persist:
            # Return a preview: total matching and sample customers
            customers, total = await preview_segment(db, rules, limit=5)
            return {
                "persisted": False,
                "total_matching": total,
                "sample_customers": [
                    {"name": c.name, "email": c.email, "total_spend": c.total_spend, "order_count": c.order_count,
                     "last_order_date": str(c.last_order_date) if c.last_order_date else None}
                    for c in customers
                ],
                "rules": rules,
                "name": name,
                "description": description,
            }

        # Persist the segment
        segment = await create_segment_with_members(
            db=db,
            name=name,
            description=description,
            rules=rules,
            natural_language_query=arguments.get("description", ""),
            is_ai_generated=True,
        )
        # Ensure DB state is visible to follow-up tool calls
        await db.flush()
        return {
            "persisted": True,
            "segment_id": str(segment.id),
            "name": segment.name,
            "customer_count": segment.customer_count,
        }

    elif tool_name == "delete_segment":
        seg_id = arguments.get("segment_id")
        if not seg_id:
            return {"error": "segment_id required"}
        result = await db.execute(select(Segment).where(Segment.id == seg_id))
        segment = result.scalar_one_or_none()
        if not segment:
            return {"error": "Segment not found"}

        # Unlink campaigns and delete segment
        await db.execute(
            update(Campaign).where(Campaign.segment_id == seg_id).values(segment_id=None)
        )
        await db.delete(segment)
        await db.flush()
        return {"deleted": True, "segment_id": seg_id}

    elif tool_name == "create_campaign":
        # Ensure segment_id is a UUID (SQLAlchemy expects a UUID object when using UUID(as_uuid=True)).
        seg_id_raw = arguments.get("segment_id")
        seg_uuid = None
        if seg_id_raw:
            try:
                seg_uuid = UUID(str(seg_id_raw))
            except Exception:
                return {"error": "invalid segment_id"}

        campaign = Campaign(
            name=arguments["name"],
            segment_id=seg_uuid,
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
        cid_raw = arguments.get("campaign_id")
        try:
            cid = UUID(str(cid_raw))
        except Exception:
            return {"error": "invalid campaign_id"}
        try:
            stats = await get_campaign_stats(db, cid)
            return stats
        except ValueError:
            return {"error": "Campaign not found"}

    elif tool_name == "send_campaign":
        cid_raw = arguments.get("campaign_id")
        try:
            cid = UUID(str(cid_raw))
        except Exception:
            return {"error": "invalid campaign_id"}
        try:
            count = await send_campaign(db, cid)
            return {
                "status": "sent",
                "recipients": count,
                "message": f"Campaign sent to {count} recipients. Delivery receipts will arrive shortly.",
            }
        except CampaignDispatchError as e:
            return {"error": str(e), "status": "failed", "recipients": e.recipient_count}
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

    # --- Quick local intent detection for simple segmentation queries ---
    # This avoids waiting on external LLM providers when the user asks to find customers.
    # Example: "Find customers who spent more than 5000"
    try:
        msg = request.message or ""
        
        # Check if user is confirming a previous preview
        if history and re.search(r"\b(yes|create|save|sure|do it)\b", msg, re.IGNORECASE):
            last_msg = history[-1]["content"]
            
            # Check for "spent more than" preview
            spent_preview_match = re.search(r"Preview: found \d+ customers who spent more than (\d+)", last_msg)
            if spent_preview_match:
                value = float(spent_preview_match.group(1))
                rules = [{"field": "total_spend", "operator": ">", "value": value}]
                segment_name = "VIP Customers" if value >= 5000 else f"Spent > {int(value)}"
                description = f"Customers who spent more than {int(value)}"
                
                segment = await create_segment_with_members(
                    db=db,
                    name=segment_name,
                    description=description,
                    rules=rules,
                    natural_language_query=f"Spent more than {value}",
                    is_ai_generated=True,
                )
                reply_text = f"Great! The segment **{segment.name}** has been successfully created with {segment.customer_count} members. What would you like to do next? We can draft a campaign for them!"
                
                conversation_id = await save_chat_turn(
                    db=db,
                    conversation_id=request.conversation_id,
                    history=history,
                    db_context=db_context,
                    user_message=msg,
                    assistant_reply=reply_text,
                )
                return ChatResponse(
                    reply=reply_text,
                    conversation_id=conversation_id,
                    actions_taken=[{
                        "type": "create_segment",
                        "arguments": {"name": segment_name, "rules": rules, "persist": True},
                        "result": {"persisted": True, "segment_id": str(segment.id), "name": segment.name, "customer_count": segment.customer_count},
                    }],
                )
            
            # Check for "inactive" preview
            inactive_preview_match = re.search(r"Preview: found \d+ customers inactive for more than (\d+) days", last_msg)
            if inactive_preview_match:
                days = int(inactive_preview_match.group(1))
                rules = [{"field": "last_order_date", "operator": "days_ago_gt", "value": days}]
                segment_name = f"Inactive Customers - {days} Days"
                description = f"Customers who have been inactive for the past {days} days"
                
                segment = await create_segment_with_members(
                    db=db,
                    name=segment_name,
                    description=description,
                    rules=rules,
                    natural_language_query=f"Inactive for {days} days",
                    is_ai_generated=True,
                )
                reply_text = f"Great! The segment **{segment.name}** has been successfully created with {segment.customer_count} members. Want me to draft a win-back campaign?"
                
                conversation_id = await save_chat_turn(
                    db=db,
                    conversation_id=request.conversation_id,
                    history=history,
                    db_context=db_context,
                    user_message=msg,
                    assistant_reply=reply_text,
                )
                return ChatResponse(
                    reply=reply_text,
                    conversation_id=conversation_id,
                    actions_taken=[{
                        "type": "create_segment",
                        "arguments": {"name": segment_name, "rules": rules, "persist": True},
                        "result": {"persisted": True, "segment_id": str(segment.id), "name": segment.name, "customer_count": segment.customer_count},
                    }],
                )

        inactive_days = parse_inactive_segment_request(msg)
        if inactive_days is not None:
            rules = [{"field": "last_order_date", "operator": "days_ago_gt", "value": inactive_days}]
            segment_name = f"Inactive Customers - {inactive_days} Days"
            description = f"Customers who have been inactive for the past {inactive_days} days"

            if wants_segment_creation(msg):
                existing_result = await db.execute(
                    select(Segment).where(func.lower(Segment.name) == segment_name.lower())
                )
                existing_segment = existing_result.scalar_one_or_none()

                if existing_segment:
                    reply_text = (
                        f'The segment "{existing_segment.name}" already exists with '
                        f"{existing_segment.customer_count} members."
                    )
                    result = {
                        "persisted": True,
                        "segment_id": str(existing_segment.id),
                        "name": existing_segment.name,
                        "customer_count": existing_segment.customer_count,
                        "already_exists": True,
                    }
                else:
                    segment = await create_segment_with_members(
                        db=db,
                        name=segment_name,
                        description=description,
                        rules=rules,
                        natural_language_query=msg,
                        is_ai_generated=True,
                    )
                    reply_text = f'Created "{segment.name}" with {segment.customer_count} members.'
                    result = {
                        "persisted": True,
                        "segment_id": str(segment.id),
                        "name": segment.name,
                        "customer_count": segment.customer_count,
                    }

                conversation_id = await save_chat_turn(
                    db=db,
                    conversation_id=request.conversation_id,
                    history=history,
                    db_context=db_context,
                    user_message=request.message,
                    assistant_reply=reply_text,
                )

                return ChatResponse(
                    reply=reply_text,
                    conversation_id=conversation_id,
                    actions_taken=[{
                        "type": "create_segment",
                        "arguments": {"name": segment_name, "description": description, "rules": rules, "persist": True},
                        "result": result,
                    }],
                )

            customers, total = await preview_segment(db, rules, limit=5)
            sample_names = [c.name for c in customers]
            reply_text = f"Preview: found {total} customers inactive for more than {inactive_days} days."
            if sample_names:
                reply_text += f" Sample members: {', '.join(sample_names)}."
            reply_text += " Say 'create this segment' to save it."

            conversation_id = await save_chat_turn(
                db=db,
                conversation_id=request.conversation_id,
                history=history,
                db_context=db_context,
                user_message=request.message,
                assistant_reply=reply_text,
            )

            return ChatResponse(
                reply=reply_text,
                conversation_id=conversation_id,
                actions_taken=[{
                    "type": "preview_segment",
                    "arguments": {"rules": rules},
                    "result": {"persisted": False, "total_matching": total, "rules": rules},
                }],
            )

        spent_match = re.search(r"(?:spent|spend)\s+(?:more\s+than|over)\s*[\₹\$\£]?\s*([0-9\.,]+)", msg, re.IGNORECASE)
        if spent_match:
            raw_num = spent_match.group(1)
            num_clean = re.sub(r"[^0-9.]", "", raw_num)
            value = float(num_clean) if num_clean else None
            if value is not None:
                rules = [{"field": "total_spend", "operator": ">", "value": value}]
                customers, total = await preview_segment(db, rules, limit=5)
                sample = [
                    {"name": c.name, "email": c.email, "total_spend": c.total_spend, "order_count": c.order_count}
                    for c in customers
                ]

                reply_text = f"Preview: found {total} customers who spent more than {int(value)}. Here are {len(sample)} samples: " + ", ".join([s["name"] for s in sample]) + ". Would you like to create this segment?"

                # Save conversation (upsert) similar to the normal flow
                conversation_id = request.conversation_id
                history = []
                if conversation_id:
                    result = await db.execute(
                        select(AIConversation).where(AIConversation.id == conversation_id)
                    )
                    conv = result.scalar_one_or_none()
                    if conv:
                        history = conv.messages or []

                if not conversation_id:
                    conversation_id = uuid4()

                history.append({"role": "user", "content": request.message})
                history.append({"role": "assistant", "content": reply_text})

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

                return ChatResponse(reply=reply_text, conversation_id=conversation_id, actions_taken=[{"type": "preview_segment", "rules": rules, "total_matching": total, "sample": sample}])
    except Exception:
        # Fall back to normal AI flow if local intent detector fails for any reason
        pass

    if wants_campaign_launch(request.message or "") and not re.search(
        r"\b(create|make|build)\b", request.message or "", re.IGNORECASE
    ):
        reply_text, launch_actions = await launch_campaign_from_chat(db, request.message or "")
        conversation_id = await save_chat_turn(
            db=db,
            conversation_id=request.conversation_id,
            history=history,
            db_context=db_context,
            user_message=request.message,
            assistant_reply=reply_text,
        )
        return ChatResponse(
            reply=reply_text,
            conversation_id=conversation_id,
            actions_taken=launch_actions,
        )

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

        if (
            tc["name"] == "create_campaign"
            and wants_campaign_launch(request.message)
            and isinstance(result, dict)
            and result.get("campaign_id")
        ):
            send_arguments = {"campaign_id": result["campaign_id"]}
            send_result = await execute_tool_call(db, "send_campaign", send_arguments)
            actions_taken.append({
                "type": "send_campaign",
                "arguments": send_arguments,
                "result": send_result,
            })
            tool_results.append(send_result)

    # If tools were called, get a follow-up response with tool results
    if tool_calls and tool_results:
        # If any tool result is a preview (persisted: False), instruct the assistant to ask for confirmation
        preview_exists = any(isinstance(r, dict) and r.get("persisted") is False for r in tool_results)
        created_segments = [
            r for r in tool_results
            if isinstance(r, dict) and r.get("persisted") is True and r.get("name") and "customer_count" in r
        ]
        sent_campaigns = [
            r for r in tool_results
            if isinstance(r, dict) and r.get("status") == "sent" and "recipients" in r
        ]
        failed_campaign_sends = [
            r for r in tool_results
            if isinstance(r, dict) and r.get("status") == "failed" and r.get("error")
        ]
        created_campaign = next(
            (
                r for r in tool_results
                if isinstance(r, dict) and r.get("campaign_id") and r.get("name")
            ),
            None,
        )

        if sent_campaigns:
            send_result = sent_campaigns[0]
            campaign_name = created_campaign["name"] if created_campaign else "the campaign"
            reply = (
                f'Created and sent "{campaign_name}" to '
                f'{send_result["recipients"]} recipients. Delivery receipts will arrive shortly.'
            )

        elif failed_campaign_sends:
            send_result = failed_campaign_sends[0]
            campaign_name = created_campaign["name"] if created_campaign else "the campaign"
            reply = f'Created "{campaign_name}", but sending failed: {send_result["error"]}'

        elif created_segments and not preview_exists:
            segment_result = created_segments[0]
            if segment_result.get("already_exists"):
                reply = (
                    f'The segment "{segment_result["name"]}" already exists with '
                    f'{segment_result["customer_count"]} members.'
                )
            else:
                reply = (
                    f'Created "{segment_result["name"]}" with '
                    f'{segment_result["customer_count"]} members.'
                )

        elif preview_exists:
            user_followup = (
                f"Tool results: {json.dumps(tool_results, default=str)}."
                " Summarize the preview for the marketer, show the sample members and total matching count, "
                "and explicitly ask whether to persist this segment. Do NOT create or persist anything unless the marketer confirms. "
                "If they confirm, they may reply with 'create' or 'yes' and include any name/description changes."
            )
        else:
            user_followup = f"Tool results: {json.dumps(tool_results, default=str)}. Please summarize these results naturally for the marketer."

        if not (sent_campaigns or failed_campaign_sends or (created_segments and not preview_exists)):
            followup_messages = history + [
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": reply or "Let me look into that..."},
                {"role": "user", "content": user_followup},
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
