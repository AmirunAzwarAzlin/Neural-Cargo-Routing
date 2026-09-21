import csv
import io
import json

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import queries
from app.auth import (
    COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    check_password,
    check_rate_limit,
    csrf_token_for_session,
    make_session_token,
    record_login_attempt,
    require_auth,
    require_csrf,
)
from config import settings

app = FastAPI(
    title="SDOC Shipping Document Verification",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _verify_csrf(csrf_token: str = Form(...), session: str = Depends(require_auth)) -> None:
    require_csrf(csrf_token, session)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
def login_submit(request: Request, password: str = Form(...)):
    client_key = _client_key(request)
    if not check_rate_limit(client_key):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Too many attempts. Please wait a minute and try again."},
            status_code=429,
        )
    record_login_attempt(client_key)
    if check_password(password):
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(
            COOKIE_NAME,
            make_session_token(),
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=SESSION_MAX_AGE_SECONDS,
        )
        return resp
    return templates.TemplateResponse(
        request, "login.html", {"error": "Wrong password."}, status_code=401
    )


@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, _: str = Depends(require_auth)):
    c = queries.client()
    summary = queries.dashboard_summary(c)
    return templates.TemplateResponse(request, "dashboard.html", {"s": summary})


@app.get("/queue", response_class=HTMLResponse)
def queue(request: Request, status: str | None = None, reason: str | None = None, _: str = Depends(require_auth)):
    c = queries.client()
    rows = queries.list_queue(c, status=status, reason=reason)
    return templates.TemplateResponse(
        request, "queue.html", {"rows": rows, "status": status, "reason": reason}
    )


@app.get("/email/{email_id}", response_class=HTMLResponse)
def email_detail(request: Request, email_id: str, session: str = Depends(require_auth)):
    c = queries.client()
    detail = queries.get_email_detail(c, email_id)
    csrf_token = csrf_token_for_session(session) if session else ""
    return templates.TemplateResponse(
        request, "detail.html", {"email_id": email_id, "d": detail, "csrf_token": csrf_token}
    )


@app.post("/email/{email_id}/correct")
def correct(
    email_id: str,
    document_id: str = Form(...),
    field: str = Form(...),
    new_value: str = Form(...),
    reason: str = Form(""),
    _csrf: None = Depends(_verify_csrf),
):
    c = queries.client()
    queries.correct_field(c, document_id, field, new_value)
    queries.apply_review_action(c, email_id, actor="human_reviewer", action="correct", field=field, reason=reason)
    return RedirectResponse(url=f"/email/{email_id}", status_code=303)


@app.post("/email/{email_id}/confirm")
def confirm(email_id: str, reason: str = Form(""), _csrf: None = Depends(_verify_csrf)):
    c = queries.client()
    queries.apply_review_action(c, email_id, actor="human_reviewer", action="confirm", field=None, reason=reason)
    return RedirectResponse(url=f"/email/{email_id}", status_code=303)


@app.post("/email/{email_id}/reject")
def reject(email_id: str, reason: str = Form(""), _csrf: None = Depends(_verify_csrf)):
    c = queries.client()
    queries.apply_review_action(c, email_id, actor="human_reviewer", action="reject", field=None, reason=reason)
    return RedirectResponse(url=f"/email/{email_id}", status_code=303)


@app.get("/export/submission.json")
def export_submission(_: str = Depends(require_auth)):
    c = queries.client()
    classifications = c.table("classifications").select("email_id,category").execute().data
    comparisons = {row["email_id"]: row for row in c.table("comparisons").select("*").execute().data}
    cat_by_email = {row["email_id"]: row["category"] for row in classifications}

    submission = {}
    for email_id, category in cat_by_email.items():
        cmp = comparisons.get(email_id)
        if cmp is None:
            submission[email_id] = {
                "category": category, "status": "OK", "review_reason": None,
                "defect_fields": [], "has_defect": False,
            }
        else:
            submission[email_id] = {
                "category": category,
                "status": cmp["status"],
                "review_reason": cmp["review_reason"],
                "defect_fields": cmp["defect_fields"],
                "has_defect": cmp["has_defect"],
            }
    return Response(content=json.dumps(submission, indent=2), media_type="application/json")


@app.get("/export/flagged.csv")
def export_flagged_csv(_: str = Depends(require_auth)):
    c = queries.client()
    comparisons = c.table("comparisons").select("*").eq("status", "MISMATCH").execute().data
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["email_id", "defect_fields"])
    for row in comparisons:
        writer.writerow([row["email_id"], ";".join(row["defect_fields"] or [])])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=flagged.csv"
    })
