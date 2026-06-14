"use client";

import { useState, useRef, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import "./chat.css";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions?: ChatAction[];
}

type ChatAction = {
  type: string;
  result?: {
    total_matching?: number;
    name?: string;
    customer_count?: number;
    recipients?: number;
    status?: string;
    message?: string;
    error?: string;
  };
};

type ChatResponse = {
  reply: string;
  conversation_id?: string;
  actions_taken?: ChatAction[];
};

const SUGGESTIONS = [
  "Find customers who spent more than ₹5,000",
  "Show me inactive customers from the last 30 days",
  "Create a WhatsApp campaign for high-value customers",
  "How many orders were placed this month?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content:
        "Hi! I'm your XENO AI assistant. I can help you analyze customer data, create audience segments, draft messages, and launch campaigns across WhatsApp, SMS, Email and more.\n\nWhat would you like to do today?",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messageIdRef = useRef(2);

  const nextMessageId = () => {
    messageIdRef.current += 1;
    return messageIdRef.current.toString();
  };

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  useEffect(() => {
    const lastMessage = messages[messages.length - 1];

    if (!lastMessage || isLoading || lastMessage.role === "user") {
      scrollToBottom();
      return;
    }

    document
      .getElementById(`chat-message-${lastMessage.id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [messages, isLoading]);

  const handleSubmit = async (text?: string) => {
    const messageText = text || input.trim();
    if (!messageText || isLoading) return;

    const userMsg: Message = {
      id: nextMessageId(),
      role: "user",
      content: messageText,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      const response = (await fetchApi("/ai/chat", {
        method: "POST",
        body: JSON.stringify({
          message: userMsg.content,
          conversation_id: conversationId,
        }),
      })) as ChatResponse;

      if (response.conversation_id && !conversationId) {
        setConversationId(response.conversation_id);
      }

      const assistantMsg: Message = {
        id: nextMessageId(),
        role: "assistant",
        content: response.reply,
        actions: response.actions_taken || [],
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: nextMessageId(),
          role: "assistant",
          content:
            "Sorry, I encountered an error. Please make sure the backend is running and the Groq/Gemini API keys are configured correctly.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Auto-resize
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 150) + "px";
  };

  const getActionIcon = (type: string) => {
    switch (type) {
      case "query_customers":
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        );
      case "create_segment":
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="16" /><line x1="8" y1="12" x2="16" y2="12" />
          </svg>
        );
      case "create_campaign":
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 2L11 13" /><path d="M22 2L15 22l-4-9-9-4 20-7z" />
          </svg>
        );
      case "send_campaign":
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        );
      default:
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="13 17 18 12 13 7" /><polyline points="6 17 11 12 6 7" />
          </svg>
        );
    }
  };

  const getActionDescription = (action: ChatAction) => {
    switch (action.type) {
      case "query_customers":
        return `Found ${action.result?.total_matching ?? "?"} matching customers`;
      case "create_segment":
        return `Created "${action.result?.name}" with ${action.result?.customer_count} members`;
      case "create_campaign":
        return `Campaign "${action.result?.name}" created`;
      case "send_campaign":
        if (action.result?.error) {
          return `Campaign send failed: ${action.result.error}`;
        }
        return `Campaign sent to ${action.result?.recipients ?? "?"} recipients`;
      default:
        return action.type;
    }
  };

  return (
    <div className="chat-page animate-fade-in" id="chat-page">
      {/* Header */}
      <div className="chat-header">
        <div>
          <h1>AI Assistant</h1>
          <p className="subtitle">
            Chat to create segments, draft messages, and launch campaigns.
          </p>
        </div>
      </div>

      {/* Chat Container */}
      <div className="chat-container glass-panel-static">
        {/* Messages Area */}
        <div className="chat-messages">
          {messages.map((msg) => (
            <div
              key={msg.id}
              id={`chat-message-${msg.id}`}
              className={`chat-message chat-message-${msg.role}`}
            >
              <div className="chat-message-avatar">
                {msg.role === "user" ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2L2 7l10 5 10-5-10-5z" />
                    <path d="M2 17l10 5 10-5" />
                    <path d="M2 12l10 5 10-5" />
                  </svg>
                )}
              </div>
              <div className="chat-message-body">
                {msg.content && msg.content.trim() !== "" && (
                  <div className="chat-message-content">{msg.content}</div>
                )}

                {/* Tool Actions */}
                {msg.actions && msg.actions.length > 0 && (
                  <div className="chat-actions">
                    <div className="chat-actions-header">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--primary-light)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                      </svg>
                      <span>Actions taken automatically</span>
                    </div>
                    {msg.actions.map((action, idx) => (
                      <div key={idx} className="chat-action-item">
                        <span className="chat-action-icon">
                          {getActionIcon(action.type)}
                        </span>
                        <span>{getActionDescription(action)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Loading indicator */}
          {isLoading && (
            <div className="chat-message chat-message-assistant">
              <div className="chat-message-avatar">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2L2 7l10 5 10-5-10-5z" />
                  <path d="M2 17l10 5 10-5" />
                  <path d="M2 12l10 5 10-5" />
                </svg>
              </div>
              <div className="chat-message-body">
                <div className="chat-message-content chat-typing">
                  <div className="typing-indicator">
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion Pills (only show if no user messages yet) */}
        {messages.length <= 1 && (
          <div className="chat-suggestions">
            {SUGGESTIONS.map((s, i) => (
              <button
                key={i}
                className="chat-suggestion-pill"
                onClick={() => handleSubmit(s)}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Input Area */}
        <div className="chat-input-area">
          <div className="chat-input-wrapper">
            <textarea
              ref={textareaRef}
              className="chat-input"
              placeholder="Ask me to find high-value customers or draft a campaign..."
              value={input}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              rows={1}
              id="chat-input"
            />
            <button
              className="chat-send-btn"
              onClick={() => handleSubmit()}
              disabled={!input.trim() || isLoading}
              id="chat-send"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
          <div className="chat-hint">
            <strong>Tip:</strong> Try &quot;Find customers who spent more than
            5000 and draft a friendly WhatsApp message.&quot;
          </div>
        </div>
      </div>
    </div>
  );
}
