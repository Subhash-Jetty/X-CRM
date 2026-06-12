"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchApi } from "@/lib/api";
import { getUser, getGreeting } from "@/lib/auth";
import { useRouter } from "next/navigation";

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingCampaigns, setLoadingCampaigns] = useState(true);
  const [creatingSegment, setCreatingSegment] = useState<string | null>(null);
  const user = getUser();
  const router = useRouter();

  useEffect(() => {
    async function loadData() {
      try {
        const data = await fetchApi("/customers/stats");
        setStats(data);
      } catch (error) {
        console.error("Failed to load stats:", error);
      } finally {
        setLoading(false);
      }
    }
    async function loadCampaigns() {
      try {
        const data = await fetchApi("/campaigns");
        // Get stats for first 4 campaigns
        const recent = data.slice(0, 4);
        const withStats = await Promise.all(
          recent.map(async (c: any) => {
            try {
              const s = await fetchApi(`/campaigns/${c.id}/stats`);
              return { ...c, stats: s };
            } catch {
              return c;
            }
          })
        );
        setCampaigns(withStats);
      } catch (error) {
        console.error("Failed to load campaigns:", error);
      } finally {
        setLoadingCampaigns(false);
      }
    }
    loadData();
    loadCampaigns();
  }, []);

  const handleCreateSegment = async (title: string, description: string) => {
    setCreatingSegment(title);
    try {
      await fetchApi("/ai/chat", {
        method: "POST",
        body: JSON.stringify({
          message: `Please create a segment for ${title}. Criteria: ${description}`
        })
      });
      router.push("/segments");
    } catch (error) {
      console.error("Failed to create segment:", error);
      alert("Failed to create segment");
    } finally {
      setCreatingSegment(null);
    }
  };

  const greeting = getGreeting();

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed": return "var(--success)";
      case "sending": case "sent": return "var(--primary-light)";
      case "draft": return "var(--text-muted)";
      default: return "var(--text-muted)";
    }
  };

  return (
    <div className="animate-fade-in">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header-left">
          <h1>
            {greeting}, {user?.name?.split(" ")[0] || "there"}
          </h1>
          <p className="subtitle">
            Here&apos;s what&apos;s happening with {user?.company || "your"} customers
            today.
          </p>
        </div>
        <Link href="/chat" className="btn btn-primary">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          Ask AI Assistant
        </Link>
      </div>

      {/* Stat Cards */}
      {loading ? (
        <div className="grid-cols-4 stagger-children" style={{ marginBottom: 32 }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="stat-card">
              <div className="skeleton skeleton-circle" style={{ width: 48, height: 48, borderRadius: 12 }} />
              <div className="stat-info">
                <div className="skeleton skeleton-line skeleton-line-short" style={{ marginBottom: 10 }} />
                <div className="skeleton skeleton-line skeleton-line-medium" style={{ height: 24 }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid-cols-4 stagger-children" style={{ marginBottom: 32 }}>
          <div className="stat-card">
            <div className="stat-icon" style={{ background: "var(--primary-glow)" }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary-light)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </div>
            <div className="stat-info">
              <div className="stat-label">Total Customers</div>
              <div className="stat-value">
                {stats?.total_customers?.toLocaleString() || "0"}
              </div>
              <div className="stat-change positive">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="18 15 12 9 6 15" /></svg>
                Active
              </div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: "var(--success-glow)" }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="1" x2="12" y2="23" />
                <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
              </svg>
            </div>
            <div className="stat-info">
              <div className="stat-label">Total Revenue</div>
              <div className="stat-value" style={{ color: "var(--success)" }}>
                &#8377;{stats?.total_revenue?.toLocaleString(undefined, { maximumFractionDigits: 0 }) || "0"}
              </div>
              <div className="stat-change positive">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="18 15 12 9 6 15" /></svg>
                Growing
              </div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: "var(--secondary-glow)" }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--secondary-light)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            </div>
            <div className="stat-info">
              <div className="stat-label">Avg Order Value</div>
              <div className="stat-value">
                &#8377;{stats?.avg_order_value?.toLocaleString(undefined, { maximumFractionDigits: 0 }) || "0"}
              </div>
              <div className="stat-change neutral">Lifetime</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: "var(--accent-glow)" }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 2L11 13" />
                <path d="M22 2L15 22l-4-9-9-4 20-7z" />
              </svg>
            </div>
            <div className="stat-info">
              <div className="stat-label">Campaigns</div>
              <div className="stat-value">
                {campaigns.length || "0"}
              </div>
              <div className="stat-change neutral">Total</div>
            </div>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ marginBottom: 16 }}>Quick Actions</h2>
        <div className="grid-cols-3">
          <Link href="/chat" className="quick-action">
            <div className="quick-action-icon" style={{ background: "var(--primary-glow)" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--primary-light)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <div>
              <div className="quick-action-text">Ask AI Assistant</div>
              <div className="quick-action-desc">Create segments &amp; campaigns with natural language</div>
            </div>
          </Link>

          <Link href="/segments" className="quick-action">
            <div className="quick-action-icon" style={{ background: "var(--secondary-glow)" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--secondary-light)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                <path d="M2 12h20" />
              </svg>
            </div>
            <div>
              <div className="quick-action-text">View Segments</div>
              <div className="quick-action-desc">Browse your customer audiences</div>
            </div>
          </Link>

          <Link href="/campaigns" className="quick-action">
            <div className="quick-action-icon" style={{ background: "var(--accent-glow)" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 2L11 13" />
                <path d="M22 2L15 22l-4-9-9-4 20-7z" />
              </svg>
            </div>
            <div>
              <div className="quick-action-text">View Campaigns</div>
              <div className="quick-action-desc">Track delivery &amp; engagement</div>
            </div>
          </Link>
        </div>
      </div>

      {/* AI Suggestions + Recent Campaigns */}
      <div className="grid-cols-2">
        <div className="card glass-panel-static" style={{ display: "flex", flexDirection: "column" }}>
          <h2>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--primary-light)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: "middle", marginRight: 8 }}>
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
            AI Suggestions
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div className="suggestion-card" style={{ borderColor: "rgba(99, 102, 241, 0.2)", background: "rgba(99, 102, 241, 0.05)" }}>
              <div className="suggestion-header">
                <span className="suggestion-title">At-Risk Churners</span>
                <span className="badge badge-warning">High Priority</span>
              </div>
              <p className="suggestion-body">
                Previously active customers who haven&apos;t ordered in 30+ days. Win them back with a personalized offer.
              </p>
              <button
                className="btn btn-secondary btn-sm"
                style={{ width: "100%" }}
                onClick={() => handleCreateSegment("At-Risk Churners", "Customers with 2+ orders who haven't ordered in 30+ days")}
                disabled={creatingSegment === "At-Risk Churners"}
              >
                {creatingSegment === "At-Risk Churners" ? "Creating Segment..." : "Ask AI to create segment"}
              </button>
            </div>

            <div className="suggestion-card">
              <div className="suggestion-header">
                <span className="suggestion-title">New VIP Customers</span>
                <span className="badge badge-success">Opportunity</span>
              </div>
              <p className="suggestion-body">
                Customers who crossed the &#8377;10,000 spend threshold. Reward their loyalty.
              </p>
              <button
                className="btn btn-secondary btn-sm"
                style={{ width: "100%" }}
                onClick={() => handleCreateSegment("New VIP Customers", "Customers who spent more than ₹10,000 total")}
                disabled={creatingSegment === "New VIP Customers"}
              >
                {creatingSegment === "New VIP Customers" ? "Creating Segment..." : "Ask AI to create segment"}
              </button>
            </div>
          </div>
        </div>

        {/* Recent Campaigns — now fetched from API */}
        <div className="card glass-panel-static" style={{ display: "flex", flexDirection: "column" }}>
          <h2>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: "middle", marginRight: 8 }}>
              <path d="M22 2L11 13" />
              <path d="M22 2L15 22l-4-9-9-4 20-7z" />
            </svg>
            Recent Campaigns
          </h2>

          {loadingCampaigns ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {[1, 2].map((i) => (
                <div key={i} style={{ padding: "16px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-default)" }}>
                  <div className="skeleton skeleton-line skeleton-line-medium" style={{ marginBottom: 8 }} />
                  <div className="skeleton skeleton-line skeleton-line-short" />
                </div>
              ))}
            </div>
          ) : campaigns.length === 0 ? (
            <div className="empty-state" style={{ padding: "40px 24px" }}>
              <div className="empty-state-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--primary-light)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 2L11 13" />
                  <path d="M22 2L15 22l-4-9-9-4 20-7z" />
                </svg>
              </div>
              <h3>No campaigns yet</h3>
              <p>Ask the AI assistant to create your first campaign.</p>
              <Link href="/chat" className="btn btn-primary btn-sm">
                Launch a campaign
              </Link>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {campaigns.map((c) => (
                <div
                  key={c.id}
                  style={{
                    padding: "16px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--border-default)",
                    background: "var(--bg-card)",
                    cursor: "pointer",
                    transition: "border-color 0.2s",
                  }}
                  onClick={() => router.push("/campaigns")}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <span style={{ fontWeight: 600, fontSize: 14, color: "var(--text-main)" }}>{c.name}</span>
                    <span
                      className={`badge ${c.status === "completed" ? "badge-success" : c.status === "draft" ? "badge-warning" : "badge-secondary"}`}
                      style={{ fontSize: 10 }}
                    >
                      {c.status.toUpperCase()}
                    </span>
                  </div>
                  <div style={{ display: "flex", gap: 16, fontSize: 12, color: "var(--text-muted)" }}>
                    <span style={{ textTransform: "capitalize" }}>{c.channel}</span>
                    {c.total_recipients > 0 && <span>{c.total_recipients} recipients</span>}
                    {c.stats?.delivery_rate > 0 && (
                      <span style={{ color: "var(--success)" }}>{c.stats.delivery_rate}% delivered</span>
                    )}
                    {c.stats?.conversion_rate > 0 && (
                      <span style={{ color: "var(--primary-light)" }}>{c.stats.conversion_rate}% converted</span>
                    )}
                  </div>
                </div>
              ))}
              <Link href="/campaigns" className="btn btn-secondary btn-sm" style={{ alignSelf: "center", marginTop: 4 }}>
                View All Campaigns
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
