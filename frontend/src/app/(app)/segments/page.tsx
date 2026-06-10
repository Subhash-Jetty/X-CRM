"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { fetchApi } from "@/lib/api";

export default function SegmentsPage() {
  const [segments, setSegments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSegmentMembers, setSelectedSegmentMembers] = useState<any[]>([]);
  const [isMembersModalOpen, setIsMembersModalOpen] = useState(false);
  const [loadingMembers, setLoadingMembers] = useState(false);

  useEffect(() => {
    loadSegments();
  }, []);

  const loadSegments = async () => {
    try {
      const data = await fetchApi("/segments");
      setSegments(data || []);
    } catch (error) {
      console.error("Failed to load segments:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleViewMembers = async (segmentId: string) => {
    setLoadingMembers(true);
    setIsMembersModalOpen(true);
    try {
      const data = await fetchApi(`/segments/${segmentId}/members?page_size=50`);
      setSelectedSegmentMembers(data.items || []);
    } catch (error) {
      console.error("Failed to load members:", error);
      alert("Failed to load members");
    } finally {
      setLoadingMembers(false);
    }
  };

  const handleDeleteSegment = async (segmentId: string) => {
    if (!confirm("Are you sure you want to delete this segment?")) return;
    try {
      await fetchApi(`/segments/${segmentId}`, { method: "DELETE" });
      loadSegments();
    } catch (error) {
      console.error("Failed to delete segment:", error);
      alert("Failed to delete segment");
    }
  };

  return (
    <div className="animate-fade-in">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header-left">
          <h1>Segments</h1>
          <p className="subtitle">
            Audiences carved out from your customer data.
          </p>
        </div>
        <Link href="/chat" className="btn btn-primary">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Create Segment
        </Link>
      </div>

      <div className="grid-cols-2 stagger-children">
        {loading ? (
          // Skeleton
          Array.from({ length: 4 }).map((_, idx) => (
            <div key={idx} className="segment-card">
              <div className="segment-header">
                <div>
                  <div className="skeleton skeleton-line skeleton-line-medium" style={{ marginBottom: 8, height: 20 }} />
                  <div className="skeleton skeleton-line skeleton-line-long" />
                </div>
              </div>
              <div className="segment-count">
                <div className="skeleton skeleton-line" style={{ width: 40, height: 32 }} />
                <div className="skeleton skeleton-line skeleton-line-short" />
              </div>
              <div className="segment-actions">
                <div className="skeleton skeleton-line" style={{ flex: 1, height: 36, borderRadius: 8 }} />
                <div className="skeleton skeleton-line" style={{ flex: 1, height: 36, borderRadius: 8 }} />
              </div>
            </div>
          ))
        ) : segments.length === 0 ? (
          // Empty State
          <div style={{ gridColumn: "1 / -1" }}>
            <div className="card glass-panel-static empty-state">
              <div className="empty-state-icon" style={{ background: "var(--secondary-glow)" }}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--secondary-light)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                  <path d="M2 12h20" />
                </svg>
              </div>
              <h3>No segments found</h3>
              <p>
                Segments group your customers based on purchase behavior, tags, and
                more. Ask the AI assistant to create one!
              </p>
              <Link href="/chat" className="btn btn-primary">
                Ask AI to create segment
              </Link>
            </div>
          </div>
        ) : (
          // Segment Cards
          segments.map((segment) => (
            <div key={segment.id} className="segment-card">
              <div className="segment-header">
                <div style={{ paddingRight: 16 }}>
                  <h3 style={{ fontSize: "18px", color: "var(--text-main)", marginBottom: "6px" }}>
                    {segment.name}
                  </h3>
                  <div style={{ fontSize: "14px", color: "var(--text-muted)", lineHeight: 1.5 }}>
                    {segment.description}
                  </div>
                </div>
                {segment.is_ai_generated && (
                  <span className="badge badge-secondary" style={{ background: "var(--secondary-glow)", color: "var(--secondary-light)", flexShrink: 0 }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4 }}>
                      <path d="M12 2L2 7l10 5 10-5-10-5z" />
                      <path d="M2 17l10 5 10-5" />
                      <path d="M2 12l10 5 10-5" />
                    </svg>
                    AI Generated
                  </span>
                )}
              </div>

              <div className="segment-count">
                <span className="segment-count-number">
                  {segment.customer_count?.toLocaleString()}
                </span>
                <span className="segment-count-label">customers</span>
              </div>

              <div className="segment-actions">
                <button className="btn btn-secondary" onClick={() => handleViewMembers(segment.id)}>View Members</button>
                <Link href="/chat" className="btn btn-primary" style={{ display: "flex", justifyContent: "center", flex: 1 }}>
                  Launch Campaign
                </Link>
                <button 
                  className="btn btn-secondary" 
                  style={{ padding: "0 10px", color: "var(--danger)", flex: "none" }}
                  onClick={() => handleDeleteSegment(segment.id)}
                  title="Delete Segment"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    <line x1="10" y1="11" x2="10" y2="17" />
                    <line x1="14" y1="11" x2="14" y2="17" />
                  </svg>
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Members Modal */}
      {isMembersModalOpen && typeof document !== "undefined" && createPortal(
        <div className="modal-overlay" style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card glass-panel-static" style={{ width: "600px", maxHeight: "80vh", display: "flex", flexDirection: "column", padding: "24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2 style={{ margin: 0 }}>Segment Members</h2>
              <button onClick={() => setIsMembersModalOpen(false)} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            </div>
            
            <div style={{ overflowY: "auto", flex: 1, paddingRight: "8px" }}>
              {loadingMembers ? (
                <div style={{ textAlign: "center", padding: "20px" }}>Loading...</div>
              ) : selectedSegmentMembers.length === 0 ? (
                <div style={{ textAlign: "center", padding: "20px" }}>No members found.</div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Total Spend</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedSegmentMembers.map(m => (
                      <tr key={m.id}>
                        <td>{m.name}</td>
                        <td>{m.email}</td>
                        <td>₹{m.total_spend?.toLocaleString() || 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
