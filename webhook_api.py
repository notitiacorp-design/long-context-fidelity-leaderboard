"""
Stripe Webhook → Context Fidelity Audit Automation.
Receives Stripe checkout.session.completed, runs audit, sends report.
"""
from __future__ import annotations

import asyncio, hashlib, json, os, tempfile
from datetime import datetime
from pathlib import Path

import stripe
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── Config ──────────────────────────────────────────
STRIPE_SK = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WH = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
FROM_MAIL = os.environ.get("FROM_EMAIL", "audit@notitia.co")

app = FastAPI(title="Notitia Context Fidelity — Webhook API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── In-memory job store (replace with SQLite in prod) ──
jobs: dict[str, dict] = {}

# ── Stripe Webhook ──────────────────────────────────
@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WH)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
    
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_details", {}).get("email", "")
        audit_id = hashlib.sha256(session["id"].encode()).hexdigest()[:12]
        
        jobs[audit_id] = {
            "id": audit_id,
            "email": customer_email,
            "stripe_session": session["id"],
            "amount": session.get("amount_total", 0) / 100,
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "document": session.get("metadata", {}).get("document_url", ""),
        }
        
        # Launch audit in background
        asyncio.create_task(_run_audit_and_email(audit_id))
        
        return JSONResponse({"status": "queued", "audit_id": audit_id})
    
    return JSONResponse({"status": "ignored", "type": event["type"]})

# ── Background Audit ────────────────────────────────
async def _run_audit_and_email(audit_id: str):
    job = jobs.get(audit_id)
    if not job:
        return
    
    job["status"] = "running"
    
    try:
        # 1. Run the audit (simplified — in prod, call core_auditor.py)
        report = await _generate_report(job)
        
        # 2. Send email
        await _send_email(job["email"], report)
        
        job["status"] = "completed"
        job["completed_at"] = datetime.now().isoformat()
    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)

async def _generate_report(job: dict) -> str:
    """Generate audit report (mock — integrate core_auditor.py in production)."""
    return f"""
Context Fidelity Audit Report
==============================
Audit ID: {job['id']}
Model: deepseek-v4-pro
Date: {datetime.now().strftime('%Y-%m-%d')}

Key Finding:
- Terminal Boundary Bias detected at position 1.00
- 100% recall at all other positions (0.00–0.90)
- Recovery at 64K+ context length

Recommendation:
- Use Attention Guard proxy for production deployments
- Avoid placing critical information in the last 50 tokens before the query

Notitia Context-Certified
""".strip()

async def _send_email(to: str, body: str):
    """Send email via SendGrid/resend — stub."""
    print(f"TO: {to}\nSUBJECT: Your Context Fidelity Audit\n\n{body}")

# ── Job Status ──────────────────────────────────────
@app.get("/audit/{audit_id}")
async def get_audit_status(audit_id: str):
    job = jobs.get(audit_id)
    if not job:
        raise HTTPException(404, "Audit not found")
    return job

# ── Health ──────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "jobs": len(jobs)}
