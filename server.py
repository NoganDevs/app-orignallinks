# server.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from email.mime.text import MIMEText
from pydantic import BaseModel, EmailStr
from starlette.status import HTTP_400_BAD_REQUEST
import smtplib, random, time

app = FastAPI()

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Config / Secrets ===
EMAIL_ADDRESS = "orignallinks@gmail.com"
EMAIL_PASSWORD = "jtbyfkneamirfgvo"  # Use App Password (Never real password)

# === Verification Settings ===
codes = {}              # In-memory storage
RATE_LIMIT = {}         # Prevent spamming
CODE_TTL = 300          # 5 minutes
MAX_TRIES = 5
RESEND_INTERVAL = 30    # Seconds between sends

# === Request Models ===
class EmailRequest(BaseModel):
    email: EmailStr

class VerifyRequest(BaseModel):
    email: EmailStr
    code: str

@app.post("/send-code")
async def send_code(data: EmailRequest):
    email = data.email
    now = time.time()

    # Rate limiting
    if email in RATE_LIMIT and now - RATE_LIMIT[email] < RESEND_INTERVAL:
        raise HTTPException(status_code=429, detail="Wait before requesting again")

    # Generate + Store
    # Clean expired or used code
    existing = codes.get(email)
    if existing and now < existing["expires"]:
        return {"success": False, "message": "A code is already active. Please wait or check your inbox."}

    code = str(random.randint(100000, 999999))
    codes[email] = {
        "code": code,
        "expires": now + CODE_TTL,
        "tries": 0
}

    RATE_LIMIT[email] = now

    # Email Template (HTML)
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #f2f2f2; padding: 30px;">
        <div style="max-width: 480px; margin: auto; background: white; border-radius: 8px; padding: 30px; box-shadow: 0 0 12px rgba(0,0,0,0.05);">
            <h2 style="color:#333;">🔐 Verify Your Email</h2>
            <p>Use the code below to verify your identity:</p>
            <div style="font-size: 32px; font-weight: bold; color: #4CAF50; margin: 20px 0;">{code}</div>
            <p>This code will expire in 5 minutes.</p>
            <p style="color:#888;font-size:13px;">If you didn't request this, please ignore it.</p>
            <hr>
            <p style="font-size:12px;color:#aaa;text-align:center;">OriginalLinks Security Team</p>
        </div>
    </body>
    </html>
    """

    try:
        msg = MIMEText(html, "html")
        msg["Subject"] = "🔐 Email Verification Code"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()

        return {"success": True, "message": "Verification code sent"}
    except Exception as e:
        return {"success": False, "message": f"Failed to send email: {str(e)}"}


@app.post("/verify-code")
async def verify_code(data: VerifyRequest):
    entry = codes.get(data.email)
    now = time.time()

    if not entry:
        return {"success": False, "message": "No code found"}

    if now > entry["expires"]:
        del codes[data.email]
        return {"success": False, "message": "Code expired"}

    if entry["tries"] >= MAX_TRIES:
        del codes[data.email]
        return {"success": False, "message": "Too many attempts"}

    if data.code != entry["code"]:
        codes[data.email]["tries"] += 1
        return {"success": False, "message": "Incorrect code"}

    # Success
    del codes[data.email]
    return {"success": True, "message": "Email verified successfully"}


if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
