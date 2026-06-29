"""
Attention Guard Proxy — fixes terminal boundary bias (position 1.00).
Inserts a semantic break token before the query to prevent instruction-masking.
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import httpx, json, os

app = FastAPI(title="Attention Guard — Notitia Proxy")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

TARGET_URL = os.environ.get("TARGET_URL", "https://api.deepseek.com/v1")
GUARD_TOKEN = "\n\n<!-- END_OF_DOCUMENT -->\n\n"

# ── Auth ────────────────────────────────────────────
VALID_TOKENS = set(os.environ.get("VALID_TOKENS", "").split(","))


@app.api_route("/{path:path}", methods=["POST", "GET", "PUT", "DELETE"])
async def proxy(request: Request, path: str):
    # Auth check
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        if VALID_TOKENS and token not in VALID_TOKENS:
            raise HTTPException(401, "Invalid subscription key")
    
    body = await request.body()
    target_path = f"/{path}" if path else ""
    
    if path == "chat/completions" and body:
        body = _apply_guard(body)
    
    # Forward headers except host
    headers = dict(request.headers)
    headers.pop("host", None)
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        resp = await client.request(
            method=request.method,
            url=f"{TARGET_URL}{target_path}",
            headers=headers,
            content=body,
        )
        
        return StreamingResponse(
            resp.aiter_bytes(),
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )


def _apply_guard(body: bytes) -> bytes:
    """Insert semantic guard break between document and instruction."""
    try:
        data = json.loads(body)
        messages = data.get("messages", [])
        
        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            if isinstance(content, str) and "DOCUMENT:" in content:
                # Insert guard token between document end and question
                parts = content.split("QUESTION:", 1)
                if len(parts) == 2:
                    messages[i]["content"] = f"{parts[0].rstrip()}{GUARD_TOKEN}QUESTION:{parts[1]}"
        
        return json.dumps(data).encode()
    except:
        return body


@app.get("/health")
async def health():
    return {"status": "ok", "target": TARGET_URL, "guard": "active"}
