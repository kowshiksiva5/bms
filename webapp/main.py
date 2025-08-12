from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import os, hmac, hashlib
import store

app = FastAPI()
templates = Jinja2Templates(directory="webapp/templates")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("WEBAPP_SECRET_KEY", "change-me"))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BOT_NAME = os.getenv("TELEGRAM_BOT_USERNAME", "")
WEBAPP_TOKEN = os.getenv("WEBAPP_TOKEN")


def verify_telegram(data: dict) -> bool:
    """Verify Telegram login data using HMAC as per docs."""
    if not BOT_TOKEN:
        return False
    auth_data = {k: v for k, v in data.items() if k != "hash"}
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(auth_data.items()))
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    h = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    return h == data.get("hash")


def get_current_user(request: Request):
    user = request.session.get("user")
    if user:
        return user
    if WEBAPP_TOKEN:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and hmac.compare_digest(auth.split(" ", 1)[1], WEBAPP_TOKEN):
            return {"id": "token"}
    raise HTTPException(status_code=401)


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    if "hash" in request.query_params:
        data = dict(request.query_params)
        if verify_telegram(data):
            request.session["user"] = {"id": data.get("id"), "username": data.get("username")}
            return RedirectResponse("/", status_code=303)
        raise HTTPException(status_code=400, detail="Invalid login")
    return templates.TemplateResponse("login.html", {"request": request, "bot_name": BOT_NAME})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user=Depends(get_current_user)):
    conn = store.connect()
    monitors = store.list_monitors(conn)
    return templates.TemplateResponse("index.html", {"request": request, "monitors": monitors, "user": user})


@app.get("/monitor/{mid}", response_class=HTMLResponse)
async def monitor_detail(mid: str, request: Request, user=Depends(get_current_user)):
    conn = store.connect()
    monitor = store.get_monitor(conn, mid)
    if not monitor:
        raise HTTPException(status_code=404)
    log_path = os.path.join("artifacts", f"{mid}.log")
    logs = ""
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            logs = f.read()[-4000:]
    return templates.TemplateResponse(
        "monitor_detail.html",
        {"request": request, "monitor": monitor, "logs": logs, "user": user},
    )


@app.post("/monitor/{mid}/edit")
async def monitor_edit(mid: str, interval_min: int = Form(...), user=Depends(get_current_user)):
    conn = store.connect()
    if not store.set_interval(conn, mid, interval_min):
        raise HTTPException(status_code=400, detail="Update failed")
    return RedirectResponse(f"/monitor/{mid}", status_code=303)
