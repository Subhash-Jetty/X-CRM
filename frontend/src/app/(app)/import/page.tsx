"use client";

import { useState, useRef } from "react";
import { fetchApi } from "@/lib/api";

type JsonRecord = Record<string, unknown>;

type ImportResponse = {
  message?: string;
  count?: number;
};

type SeedCustomer = {
  name: string;
  email: string;
  phone?: string;
  tags?: string[];
};

type CustomerPageResponse = {
  items?: SeedCustomer[];
};

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export default function ImportPage() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [progress, setProgress] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setStatus("idle");
    setProgress("Reading file...");

    try {
      const text = await file.text();
      const data = JSON.parse(text) as unknown;

      // Detect file type: customers or orders
      if (isRecord(data) && Array.isArray(data.customers)) {
        setProgress(`Uploading ${data.customers.length} customers...`);
        const result = (await fetchApi("/customers/ingest", {
          method: "POST",
          body: JSON.stringify({ customers: data.customers }),
        })) as ImportResponse;
        setStatus("success");
        setMessage(result.message || `Successfully ingested ${data.customers.length} customers`);
      } else if (isRecord(data) && Array.isArray(data.orders)) {
        // Chunk orders to avoid request size limits
        const chunkSize = 500;
        const orders = data.orders;
        let totalIngested = 0;

        for (let i = 0; i < orders.length; i += chunkSize) {
          const chunk = orders.slice(i, i + chunkSize);
          setProgress(`Uploading orders: ${Math.min(i + chunkSize, orders.length)}/${orders.length}...`);
          const result = (await fetchApi("/orders/ingest", {
            method: "POST",
            body: JSON.stringify({ orders: chunk }),
          })) as ImportResponse;
          totalIngested += result.count || chunk.length;
        }

        setStatus("success");
        setMessage(`Successfully ingested ${totalIngested} orders and updated customer aggregates`);
      } else if (Array.isArray(data)) {
        // Try to detect if it's a flat array of customers or orders
        const sample = data[0];
        if (sample && ("amount" in sample || "items" in sample || "order_number" in sample)) {
          setProgress(`Uploading ${data.length} orders...`);
          const chunkSize = 500;
          let totalIngested = 0;
          for (let i = 0; i < data.length; i += chunkSize) {
            const chunk = data.slice(i, i + chunkSize);
            setProgress(`Uploading orders: ${Math.min(i + chunkSize, data.length)}/${data.length}...`);
            await fetchApi("/orders/ingest", {
              method: "POST",
              body: JSON.stringify({ orders: chunk }),
            });
            totalIngested += chunk.length;
          }
          setStatus("success");
          setMessage(`Successfully ingested ${totalIngested} orders`);
        } else {
          setProgress(`Uploading ${data.length} customers...`);
          await fetchApi("/customers/ingest", {
            method: "POST",
            body: JSON.stringify({ customers: data }),
          });
          setStatus("success");
          setMessage(`Successfully ingested ${data.length} customers`);
        }
      } else {
        throw new Error("Unrecognized JSON format. Expected { customers: [...] } or { orders: [...] }");
      }
    } catch (error: unknown) {
      setStatus("error");
      setMessage(getErrorMessage(error, "Failed to process file. Check the format and try again."));
    } finally {
      setLoading(false);
      setProgress("");
      // Reset file input
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSeedData = async () => {
    setLoading(true);
    setStatus("idle");
    setMessage("");

    try {
      // Step 1: Generate and ingest sample customers
      setProgress("Generating sample customer data...");
      const sampleCustomers = generateSampleCustomers(50);
      await fetchApi("/customers/ingest", {
        method: "POST",
        body: JSON.stringify({ customers: sampleCustomers }),
      });

      // Step 2: Generate and ingest sample orders
      setProgress("Generating sample order data...");
      // We need customer emails to link orders
      const customersResp = (await fetchApi("/customers?page_size=100")) as CustomerPageResponse;
      const existingCustomers = customersResp.items || [];

      if (existingCustomers.length > 0) {
        const sampleOrders = generateSampleOrders(existingCustomers, 200);
        setProgress(`Ingesting ${sampleOrders.length} orders...`);
        await fetchApi("/orders/ingest", {
          method: "POST",
          body: JSON.stringify({ orders: sampleOrders }),
        });
      }

      setStatus("success");
      setMessage(`Demo data loaded! ${sampleCustomers.length} customers and 200 orders ingested successfully.`);
    } catch (error: unknown) {
      setStatus("error");
      setMessage(getErrorMessage(error, "Failed to load demo data. Make sure the backend is running."));
    } finally {
      setLoading(false);
      setProgress("");
    }
  };

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Data Import</h1>
          <p className="subtitle">
            Bring your customer and order data into XENO.
          </p>
        </div>
      </div>

      <div className="grid-cols-2">
        {/* File Upload */}
        <div className="card glass-panel-static">
          <h2 style={{ marginBottom: 8 }}>JSON Upload</h2>
          <p
            style={{
              color: "var(--text-muted)",
              marginBottom: "24px",
              fontSize: "14px",
            }}
          >
            Upload a <code style={{ background: "var(--bg-root)", padding: "2px 6px", borderRadius: 4, fontSize: 12 }}>customers.json</code> or <code style={{ background: "var(--bg-root)", padding: "2px 6px", borderRadius: 4, fontSize: 12 }}>orders.json</code> file.
          </p>

          <div
            className="drop-zone"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); e.currentTarget.style.borderColor = "var(--primary)"; }}
            onDragLeave={(e) => { e.currentTarget.style.borderColor = ""; }}
            onDrop={(e) => {
              e.preventDefault();
              e.currentTarget.style.borderColor = "";
              const file = e.dataTransfer.files[0];
              if (file && fileInputRef.current) {
                const dt = new DataTransfer();
                dt.items.add(file);
                fileInputRef.current.files = dt.files;
                fileInputRef.current.dispatchEvent(new Event("change", { bubbles: true }));
              }
            }}
            style={{ cursor: "pointer" }}
          >
            <div className="drop-zone-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary-light)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <p className="drop-zone-text">Click or drag JSON files to upload</p>
            <p className="drop-zone-hint">Supports customers.json and orders.json format</p>

            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              onChange={handleFileUpload}
              style={{ display: "none" }}
            />
          </div>

          <div style={{ marginTop: 16, fontSize: 12, color: "var(--text-muted)" }}>
            <strong>Expected formats:</strong>
            <pre style={{ marginTop: 8, padding: 12, background: "var(--bg-root)", borderRadius: 8, overflow: "auto", fontSize: 11, lineHeight: 1.5 }}>
{`{ "customers": [
    { "name": "...", "email": "...", 
      "phone": "..." }
  ] }

{ "orders": [
    { "customer_email": "...",
      "amount": 500,
      "items": [{"name":"...", "price":250, "quantity":2}],
      "channel": "online" }
  ] }`}
            </pre>
          </div>
        </div>

        {/* Demo Seed Data */}
        <div className="card glass-panel-static">
          <h2 style={{ marginBottom: 8 }}>Demo Seed Data</h2>
          <p
            style={{
              color: "var(--text-muted)",
              marginBottom: "24px",
              fontSize: "14px",
            }}
          >
            Populate your workspace with realistic generated data for BeanBox
            Coffee to test all CRM features.
          </p>

          <div style={{ padding: "32px 0", textAlign: "center" }}>
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 24 }}>
              <div style={{ width: 80, height: 80, borderRadius: "50%", background: "var(--success-glow)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                 <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2v20" />
                  <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                </svg>
              </div>
            </div>

            <button
              className="btn btn-primary btn-lg"
              onClick={handleSeedData}
              disabled={loading}
              style={{ width: "100%", maxWidth: 300, margin: "0 auto" }}
            >
              {loading ? (
                <>
                  <span className="auth-spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                  {progress || "Processing..."}
                </>
              ) : (
                "Load Demo Data"
              )}
            </button>

            {message && (
              <div
                style={{
                  marginTop: "24px",
                  padding: "16px",
                  backgroundColor: status === "error" ? "rgba(239, 68, 68, 0.1)" : "rgba(16, 185, 129, 0.1)",
                  border: `1px solid ${status === "error" ? "rgba(239, 68, 68, 0.2)" : "rgba(16, 185, 129, 0.2)"}`,
                  color: status === "error" ? "var(--danger)" : "var(--success)",
                  borderRadius: "var(--radius-md)",
                  fontSize: "14px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 8
                }}
              >
                {status === "success" && (
                   <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                    <polyline points="22 4 12 14.01 9 11.01" />
                  </svg>
                )}
                {message}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sample Data Generators ──────────────────────────

function generateSampleCustomers(count: number): SeedCustomer[] {
  const firstNames = ["Amit", "Priya", "Rahul", "Sneha", "Vikram", "Ananya", "Rohit", "Neha", "Arjun", "Kavya", "Sanjay", "Divya", "Karan", "Pooja", "Aditya", "Riya", "Manish", "Simran", "Nikhil", "Megha"];
  const lastNames = ["Sharma", "Patel", "Singh", "Gupta", "Kumar", "Mehta", "Joshi", "Verma", "Reddy", "Nair", "Chopra", "Bhat", "Iyer", "Rao", "Malhotra"];
  const tags = ["coffee-lover", "frequent-buyer", "weekend-visitor", "app-user", "loyalty-member", "new-customer", "premium"];
  const customers: SeedCustomer[] = [];

  for (let i = 0; i < count; i++) {
    const first = firstNames[Math.floor(Math.random() * firstNames.length)];
    const last = lastNames[Math.floor(Math.random() * lastNames.length)];
    const customerTags = [];
    for (const tag of tags) {
      if (Math.random() < 0.3) customerTags.push(tag);
    }
    customers.push({
      name: `${first} ${last}`,
      email: `${first.toLowerCase()}.${last.toLowerCase()}${i}@example.com`,
      phone: `+91${Math.floor(7000000000 + Math.random() * 3000000000)}`,
      tags: customerTags,
    });
  }
  return customers;
}

function generateSampleOrders(customers: SeedCustomer[], count: number) {
  const items = [
    { name: "Espresso", price: 180 },
    { name: "Cappuccino", price: 250 },
    { name: "Cold Brew", price: 280 },
    { name: "Latte", price: 220 },
    { name: "Mocha", price: 300 },
    { name: "Americano", price: 200 },
    { name: "Croissant", price: 150 },
    { name: "Muffin", price: 120 },
    { name: "Sandwich", price: 250 },
    { name: "Cookie Pack", price: 180 },
  ];
  const channels = ["online", "in-store", "app"];
  const orders = [];

  for (let i = 0; i < count; i++) {
    const customer = customers[Math.floor(Math.random() * customers.length)];
    const numItems = 1 + Math.floor(Math.random() * 3);
    const orderItems = [];
    let total = 0;

    for (let j = 0; j < numItems; j++) {
      const item = items[Math.floor(Math.random() * items.length)];
      const qty = 1 + Math.floor(Math.random() * 2);
      orderItems.push({ name: item.name, price: item.price, quantity: qty });
      total += item.price * qty;
    }

    // Random date in the last 90 days
    const daysAgo = Math.floor(Math.random() * 90);
    const date = new Date();
    date.setDate(date.getDate() - daysAgo);

    orders.push({
      customer_email: customer.email,
      amount: total,
      items: orderItems,
      channel: channels[Math.floor(Math.random() * channels.length)],
      status: "completed",
      created_at: date.toISOString(),
    });
  }
  return orders;
}
