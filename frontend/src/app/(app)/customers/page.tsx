"use client";

import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { fetchApi } from "@/lib/api";

type Customer = {
  id: string;
  name: string;
  email?: string | null;
  phone?: string | null;
  order_count?: number;
  total_spend?: number;
  last_order_date?: string | null;
  tags?: string[];
};

type CustomerPageResponse = {
  items?: Customer[];
  total?: number;
  page?: number;
  total_pages?: number;
};

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newCustomer, setNewCustomer] = useState({ name: "", email: "", phone: "" });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const loadCustomers = useCallback(async (searchQuery = "", pageNum = 1) => {
    setLoading(true);
    try {
      const url = searchQuery
        ? `/customers?search=${encodeURIComponent(searchQuery)}&page=${pageNum}`
        : `/customers?page=${pageNum}`;
      const data = (await fetchApi(url)) as CustomerPageResponse;
      setCustomers(data.items || []);
      setTotalPages(data.total_pages || 1);
    } catch (error) {
      console.error("Failed to load customers:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => loadCustomers());
  }, [loadCustomers]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    void loadCustomers(search, 1);
  };

  const handleAddCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await fetchApi("/customers/ingest", {
        method: "POST",
        body: JSON.stringify({
          customers: [{
            name: newCustomer.name,
            email: newCustomer.email || null,
            phone: newCustomer.phone || null,
            tags: []
          }]
        }),
      });
      setIsModalOpen(false);
      setNewCustomer({ name: "", email: "", phone: "" });
      setPage(1);
      void loadCustomers(search, 1);
    } catch (error) {
      console.error("Failed to add customer:", error);
      alert("Failed to add customer.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="animate-fade-in">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header-left">
          <h1>Customers</h1>
          <p className="subtitle">
            Manage your shopper base and view purchase history.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setIsModalOpen(true)}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Customer
        </button>
      </div>

      <div className="card glass-panel-static">
        {/* Search Bar */}
        <div style={{ marginBottom: "24px", display: "flex", gap: "16px" }}>
          <form
            onSubmit={handleSearch}
            style={{ flex: 1, display: "flex", gap: "12px" }}
          >
            <div className="search-bar">
              <svg className="search-bar-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                className="input-field"
                placeholder="Search by name, email, or phone..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <button type="submit" className="btn btn-secondary">
              Search
            </button>
          </form>
        </div>

        {/* Data Table */}
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Customer</th>
                <th>Contact</th>
                <th>Orders</th>
                <th>Total Spend</th>
                <th>Last Order</th>
                <th>Tags</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                // Skeleton Loading State
                Array.from({ length: 5 }).map((_, idx) => (
                  <tr key={idx}>
                    <td>
                      <div className="skeleton-row">
                        <div className="skeleton skeleton-circle" />
                        <div className="skeleton skeleton-line skeleton-line-short" />
                      </div>
                    </td>
                    <td>
                      <div className="skeleton-row" style={{ padding: 0 }}>
                        <div className="skeleton skeleton-line skeleton-line-medium" />
                      </div>
                    </td>
                    <td>
                      <div className="skeleton skeleton-line" style={{ width: 30 }} />
                    </td>
                    <td>
                      <div className="skeleton skeleton-line skeleton-line-short" />
                    </td>
                    <td>
                      <div className="skeleton skeleton-line skeleton-line-short" />
                    </td>
                    <td>
                      <div className="skeleton skeleton-line skeleton-line-short" style={{ borderRadius: 12 }} />
                    </td>
                  </tr>
                ))
              ) : customers.length === 0 ? (
                // Empty State
                <tr>
                  <td
                    colSpan={6}
                    style={{ textAlign: "center", padding: "60px 24px" }}
                  >
                    <div className="empty-state" style={{ padding: 0 }}>
                      <div className="empty-state-icon">
                        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--primary-light)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                          <circle cx="9" cy="7" r="4" />
                          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                        </svg>
                      </div>
                      <h3 style={{ marginBottom: 8 }}>No customers found</h3>
                      <p>Try adjusting your search or generate seed data.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                // Data Rows
                customers.map((c) => {
                  const initials = (c.name || "Unknown")
                    .split(" ")
                    .map((w: string) => w[0])
                    .join("")
                    .toUpperCase()
                    .slice(0, 2);

                  // Assign a consistent gradient background based on ID char code
                  const gradientIndex =
                    c.id.charCodeAt(c.id.length - 1) % 3;
                  const bg =
                    gradientIndex === 0
                      ? "var(--gradient-primary)"
                      : gradientIndex === 1
                      ? "linear-gradient(135deg, var(--accent), var(--primary))"
                      : "linear-gradient(135deg, var(--secondary), var(--primary))";

                  return (
                    <tr key={c.id}>
                      <td>
                        <div className="customer-cell">
                          <div
                            className="customer-avatar"
                            style={{ background: bg }}
                          >
                            {initials}
                          </div>
                          <span className="customer-name">{c.name}</span>
                        </div>
                      </td>
                      <td>
                        <div style={{ fontSize: "13px" }}>{c.email}</div>
                        <div
                          style={{
                            fontSize: "12px",
                            color: "var(--text-muted)",
                            marginTop: 2,
                          }}
                        >
                          {c.phone}
                        </div>
                      </td>
                      <td style={{ fontWeight: 500 }}>{c.order_count}</td>
                      <td
                        style={{
                          fontWeight: 500,
                          color:
                            (c.total_spend || 0) > 5000
                              ? "var(--success)"
                              : "inherit",
                        }}
                      >
                        &#8377;{c.total_spend?.toLocaleString() || 0}
                      </td>
                      <td
                        style={{
                          color: "var(--text-muted)",
                          fontSize: "14px",
                        }}
                      >
                        {c.last_order_date
                          ? new Date(c.last_order_date).toLocaleDateString(
                              undefined,
                              {
                                year: "numeric",
                                month: "short",
                                day: "numeric",
                              }
                            )
                          : "Never"}
                      </td>
                      <td>
                        <div
                          style={{
                            display: "flex",
                            gap: "6px",
                            flexWrap: "wrap",
                          }}
                        >
                          {c.tags?.map((tag: string) => (
                            <span key={tag} className="badge badge-neutral">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div style={{ padding: "16px 24px", display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--border-subtle)" }}>
            <button 
              className="btn btn-secondary" 
              disabled={page === 1}
              onClick={() => {
                const newPage = page - 1;
                setPage(newPage);
                void loadCustomers(search, newPage);
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
                <polyline points="15 18 9 12 15 6"></polyline>
              </svg>
              Previous
            </button>
            <span style={{ fontSize: "14px", color: "var(--text-muted)", fontWeight: 500 }}>
              Page {page} of {totalPages}
            </span>
            <button 
              className="btn btn-secondary" 
              disabled={page === totalPages}
              onClick={() => {
                const newPage = page + 1;
                setPage(newPage);
                void loadCustomers(search, newPage);
              }}
            >
              Next
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: 6 }}>
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </button>
          </div>
        )}
      </div>

      {/* Add Customer Modal */}
      {isModalOpen && typeof document !== "undefined" && createPortal(
        <div className="modal-overlay" style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card glass-panel-static" style={{ width: "400px", padding: "24px", zIndex: 1001 }}>
            <h2 style={{ marginBottom: "16px" }}>Add New Customer</h2>
            <form onSubmit={handleAddCustomer} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div>
                <label style={{ display: "block", marginBottom: "8px", fontSize: "14px", color: "var(--text-muted)" }}>Name *</label>
                <input 
                  type="text" 
                  className="input-field" 
                  value={newCustomer.name} 
                  onChange={e => setNewCustomer({...newCustomer, name: e.target.value})} 
                  required 
                  style={{ width: "100%" }}
                />
              </div>
              <div>
                <label style={{ display: "block", marginBottom: "8px", fontSize: "14px", color: "var(--text-muted)" }}>Email</label>
                <input 
                  type="email" 
                  className="input-field" 
                  value={newCustomer.email} 
                  onChange={e => setNewCustomer({...newCustomer, email: e.target.value})} 
                  style={{ width: "100%" }}
                />
              </div>
              <div>
                <label style={{ display: "block", marginBottom: "8px", fontSize: "14px", color: "var(--text-muted)" }}>Phone</label>
                <input 
                  type="text" 
                  className="input-field" 
                  value={newCustomer.phone} 
                  onChange={e => setNewCustomer({...newCustomer, phone: e.target.value})} 
                  style={{ width: "100%" }}
                />
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "8px" }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsModalOpen(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? "Adding..." : "Add Customer"}
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
