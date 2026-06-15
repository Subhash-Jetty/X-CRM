"""
AI Agent service — the brain behind the chat-first CRM experience.
Uses Groq (primary, blazing fast) with Gemini 2.5 Flash as fallback.
"""
import json
import logging
import asyncio
from uuid import UUID
from datetime import datetime
from groq import AsyncGroq
from google.api_core.exceptions import ResourceExhausted
import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)

# Timeouts (seconds)
AI_CHAT_OVERALL_TIMEOUT = getattr(settings, "AI_CHAT_TIMEOUT", 30.0)
GROQ_CALL_TIMEOUT = getattr(settings, "GROQ_TIMEOUT", 15.0)
GEMINI_CALL_TIMEOUT = getattr(settings, "GEMINI_TIMEOUT", 20.0)
AI_CHAT_MAX_TOKENS = int(getattr(settings, "AI_CHAT_MAX_TOKENS", 8192))

# Initialize AI clients
groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY, timeout=GROQ_CALL_TIMEOUT) if settings.GROQ_API_KEY else None


def init_gemini():
    if settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        return genai.GenerativeModel("gemini-2.5-flash")
    return None


gemini_model = init_gemini()


# ──────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are XENO AI, the intelligent marketing assistant for BeanBox Coffee — a premium coffee chain brand. You help marketers understand their customers, create targeted segments, craft personalized messages, and launch campaigns.

## Your Capabilities (Tools)
You have access to these tools to help the marketer:

1. **query_customers** — Query customer data with filters. Returns matching customers and count.
   Parameters: filters (list of {field, operator, value})
   Available fields: total_spend, order_count, last_order_date, avg_order_value, tags, name, email
   Available operators: >, <, >=, <=, ==, !=, days_ago_gt, days_ago_lt, contains, array_contains

2. **create_segment** — Create a customer segment from rules.
   Parameters: name (str), description (str), rules (list of {field, operator, value})
    Note: by default the agent should only *preview* a segment and return matching counts/sample customers. To persist a segment it must pass `persist=true` explicitly when calling the tool.

3. **draft_message** — Draft a personalized marketing message.
   Parameters: segment_description (str), channel (whatsapp/sms/email/rcs), tone (friendly/urgent/professional/playful), offer (str, optional)

4. **create_campaign** — Create a campaign targeting a segment.
   Parameters: name (str), segment_id (str), message_template (str), channel (str)

5. **send_campaign** — Send a campaign that's been created. This dispatches all communications to the channel service.
   Parameters: campaign_id (str)

6. **get_campaign_stats** — Get performance stats for a campaign.
   Parameters: campaign_id (str)

7. **get_insights** — Get general business insights and suggestions.
   Parameters: none

## Rules
- Always be helpful, concise, and actionable.
- When creating segments, explain what rules you're using and why.
- When drafting messages, use {{name}} or {{first_name}} for personalization, and {{total_spend}}, {{order_count}} as available placeholders.
- Before sending/creating anything, confirm with the marketer.
- Provide data-driven recommendations when possible.
- For channels: WhatsApp has highest engagement, Email is cheapest, SMS is direct, RCS is richest.
- Always respond in a structured, easy-to-read format.
- After creating a campaign, always offer to send it immediately.
- When showing stats, always include the conversion rate (orders attributed to the campaign).
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_customers",
            "description": "Query and filter customers from the database. Use this to answer questions about customer data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string", "enum": ["total_spend", "order_count", "last_order_date", "avg_order_value", "name", "email"]},
                                "operator": {"type": "string", "enum": [">", "<", ">=", "<=", "==", "!=", "days_ago_gt", "days_ago_lt", "contains", "array_contains"]},
                                "value": {"type": ["string", "number"]}
                            },
                            "required": ["field", "operator", "value"]
                        },
                        "description": "List of filter rules to apply"
                    }
                },
                "required": ["filters"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_segment",
            "description": "Create a new customer segment with the given rules. Use this when the marketer wants to define an audience. By default this returns a preview unless `persist: true` is provided.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name for the segment"},
                    "description": {"type": "string", "description": "Description of the segment"},
                    "rules": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "operator": {"type": "string"},
                                "value": {"type": ["string", "number"]}
                            },
                            "required": ["field", "operator", "value"]
                        }
                    },
                    "persist": {"type": "boolean", "description": "If true, persist the segment. Otherwise return a preview only."}
                },
                "required": ["name", "description", "rules"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_segment",
            "description": "Delete an existing segment by id. Use only when the marketer confirms deletion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "segment_id": {"type": "string", "description": "UUID of the segment to delete"}
                },
                "required": ["segment_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "draft_message",
            "description": "Draft a personalized marketing message for a customer segment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "segment_description": {"type": "string", "description": "Description of who the message is for"},
                    "channel": {"type": "string", "enum": ["whatsapp", "sms", "email", "rcs"]},
                    "tone": {"type": "string", "enum": ["friendly", "urgent", "professional", "playful"]},
                    "offer": {"type": "string", "description": "Any specific offer or promotion to include"}
                },
                "required": ["segment_description", "channel", "tone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_campaign",
            "description": "Create a campaign to send messages to a segment. Use after a segment and message are ready.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Campaign name"},
                    "segment_id": {"type": "string", "description": "UUID of the target segment"},
                    "message_template": {"type": "string", "description": "The message template to send"},
                    "channel": {"type": "string", "enum": ["whatsapp", "sms", "email", "rcs"]}
                },
                "required": ["name", "segment_id", "message_template", "channel"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaign_stats",
            "description": "Get delivery and engagement statistics for a campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "UUID of the campaign"}
                },
                "required": ["campaign_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_insights",
            "description": "Get business insights and AI-powered suggestions for the marketer.",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_campaign",
            "description": "Send/dispatch a campaign that has been created. This sends all communications to the audience via the channel service.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "UUID of the campaign to send"}
                },
                "required": ["campaign_id"]
            }
        }
    },
]

async def chat_with_ai(
    message: str,
    conversation_history: list[dict],
    db_context: dict | None = None,
) -> tuple[str, list[dict]]:
    """
    Send a message to the AI agent and get a response.
    Returns (reply_text, tool_calls_made).

    Uses Groq as primary (fast), falls back to Gemini.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add DB context if available
    if db_context:
        context_msg = f"\n\nCurrent database context:\n{json.dumps(db_context, indent=2, default=str)}"
        messages[0]["content"] += context_msg

    # Add conversation history
    messages.extend(conversation_history)

    # Add current message
    messages.append({"role": "user", "content": message})

    tool_calls_made: list[dict] = []

    async def _call_providers() -> tuple[str | None, list[dict]]:
        # Try Groq first
        if groq_client:
            try:
                response = await asyncio.wait_for(
                    groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=messages,
                        tools=TOOL_DEFINITIONS,
                        tool_choice="auto",
                        temperature=0.7,
                        max_tokens=AI_CHAT_MAX_TOKENS,
                    ),
                    timeout=GROQ_CALL_TIMEOUT,
                )

                assistant_message = response.choices[0].message

                # Check if AI wants to call tools
                if getattr(assistant_message, "tool_calls", None):
                    for tc in assistant_message.tool_calls:
                        try:
                            tool_calls_made.append({
                                "name": tc.function.name,
                                "arguments": json.loads(tc.function.arguments),
                            })
                        except Exception:
                            logger.exception("Failed to parse tool call arguments from Groq response")

                    return assistant_message.content or "", tool_calls_made

                return assistant_message.content or "I'm not sure how to help with that.", tool_calls_made

            except asyncio.TimeoutError:
                logger.warning("Groq chat call timed out after %s seconds", GROQ_CALL_TIMEOUT)
            except Exception:
                logger.exception("Groq provider error, falling back to Gemini")

        # Fallback to Gemini
        if gemini_model:
            try:
                # Convert messages to Gemini format
                gemini_history = []
                for msg in messages[1:]:  # Skip system (handled differently)
                    role = "user" if msg["role"] == "user" else "model"
                    if not gemini_history and role == "model":
                        continue  # Gemini requires history to start with a user message
                    gemini_history.append({"role": role, "parts": [msg["content"]]})

                response = await asyncio.wait_for(
                    gemini_model.generate_content_async(
                        gemini_history,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.7,
                            max_output_tokens=AI_CHAT_MAX_TOKENS,
                        ),
                    ),
                    timeout=GEMINI_CALL_TIMEOUT,
                )
                return response.text or "I'm not sure how to help with that.", tool_calls_made

            except asyncio.TimeoutError:
                logger.warning("Gemini call timed out after %s seconds", GEMINI_CALL_TIMEOUT)
            except ResourceExhausted:
                logger.warning("Gemini provider quota exhausted")
                return (
                    "The Gemini free-tier quota is temporarily exhausted. "
                    "Please try again after the quota window resets, or use Groq as the active provider.",
                    tool_calls_made,
                )
            except Exception:
                logger.exception("Gemini provider error")

        return None, tool_calls_made

    try:
        reply, calls = await asyncio.wait_for(_call_providers(), timeout=AI_CHAT_OVERALL_TIMEOUT)
        # _call_providers returns (None, []) when both providers failed or timed out
        if reply is None:
            return "I'm experiencing some issues right now. Please try again in a moment.", calls
        return reply, calls
    except asyncio.TimeoutError:
        logger.error("AI chat overall timeout after %s seconds", AI_CHAT_OVERALL_TIMEOUT)
        return "AI provider timed out. Please try again later.", tool_calls_made
    except Exception:
        logger.exception("Unexpected error in chat_with_ai")
        return "I'm experiencing some issues right now. Please try again in a moment.", tool_calls_made


async def generate_message_draft(
    segment_description: str,
    channel: str,
    tone: str,
    offer: str | None = None,
) -> str:
    """Generate a marketing message draft using AI."""
    prompt = f"""Draft a {tone} marketing message for {channel} channel.

Target audience: {segment_description}
{f'Special offer: {offer}' if offer else ''}

Requirements:
- Use {{{{name}}}} for personalization
- Keep it concise (WhatsApp/SMS: 2-3 lines, Email: short paragraph, RCS: with call-to-action)
- Be engaging and on-brand for a premium coffee chain
- Include a clear call-to-action
- Only return the message text, no explanations"""

    try:
        if groq_client:
            response = await asyncio.wait_for(
                groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.8,
                    max_tokens=500,
                ),
                timeout=10.0
            )
            return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"Groq failed for message draft: {e}")

    try:
        if gemini_model:
            response = await asyncio.wait_for(
                gemini_model.generate_content_async(prompt),
                timeout=15.0
            )
            return response.text.strip()
    except ResourceExhausted:
        logger.warning("Gemini quota exhausted for message draft")
    except Exception as e:
        logger.error(f"Both providers failed for message draft: {e}")

    return f"Hey {{{{name}}}}! We have something special for you. Visit BeanBox today! 🎉"


async def generate_segment_suggestions(customer_stats: dict) -> list[dict]:
    """AI generates segment suggestions based on customer data patterns."""
    prompt = f"""Based on these customer statistics for BeanBox Coffee:
{json.dumps(customer_stats, indent=2)}

Suggest 3-4 actionable customer segments that a marketer should target. For each, provide:
1. A catchy segment name
2. A brief description
3. The filter rules as JSON: [{{"field": "...", "operator": "...", "value": ...}}]
4. A suggested campaign action

Available fields: total_spend, order_count, last_order_date, avg_order_value
Available operators: >, <, >=, <=, days_ago_gt, days_ago_lt

Return as a JSON array of objects with keys: name, description, rules, suggested_action
Only return valid JSON, no markdown or explanation."""

    try:
        if groq_client:
            response = await asyncio.wait_for(
                groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=1000,
                    response_format={"type": "json_object"},
                ),
                timeout=15.0
            )
            content = response.choices[0].message.content
            result = json.loads(content)
            # Handle both {"suggestions": [...]} and [...] formats
            if isinstance(result, dict):
                return result.get("suggestions", result.get("segments", []))
            return result
    except Exception as e:
        logger.warning(f"AI segment suggestions failed: {e}")

    # Fallback: hardcoded suggestions
    return [
        {
            "name": "High-Value Loyalists",
            "description": "Customers who've spent over ₹5,000 with 5+ orders",
            "rules": [
                {"field": "total_spend", "operator": ">", "value": 5000},
                {"field": "order_count", "operator": ">=", "value": 5}
            ],
            "suggested_action": "Send exclusive loyalty rewards"
        },
        {
            "name": "At-Risk Churners",
            "description": "Previously active customers who haven't ordered in 30+ days",
            "rules": [
                {"field": "order_count", "operator": ">=", "value": 2},
                {"field": "last_order_date", "operator": "days_ago_gt", "value": 30}
            ],
            "suggested_action": "Win-back campaign with special offer"
        },
        {
            "name": "New Customers",
            "description": "Recently acquired customers with only 1 order",
            "rules": [
                {"field": "order_count", "operator": "==", "value": 1},
                {"field": "last_order_date", "operator": "days_ago_lt", "value": 14}
            ],
            "suggested_action": "Welcome series with second-purchase discount"
        },
    ]
