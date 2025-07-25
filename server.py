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
async def send_code(data: EmailRequest, request: Request):
    email = data.email
    now = time.time()

    # Rate limiting
    if email in RATE_LIMIT and now - RATE_LIMIT[email] < RESEND_INTERVAL:
        raise HTTPException(status_code=429, detail="Wait before requesting again")

    # 👉 Check if it's a forced resend
    is_resend = request.query_params.get("resend") == "true"

    # 🧠 Only block if it's not a resend
    if not is_resend:
        existing = codes.get(email)
        if existing and now < existing["expires"]:
            return {
                "success": False,
                "message": "Code already sent",
                "already_sent": True,
                "expires_in": int(existing["expires"] - now)
            }

    # Force fresh code (normal send or manual resend)
    code = str(random.randint(100000, 999999))
    codes[email] = {
        "code": code,
        "expires": now + CODE_TTL,
        "tries": 0
    }

    RATE_LIMIT[email] = now

    # ... send email as before ...


    # 🔐 Email sending...
    # (unchanged HTML template & SMTP logic)


    # Email Template (HTML)
    html = f"""
    <html>
  <body style="margin:0; padding:0; background:#edf0f5; font-family:'Helvetica Neue',Arial,sans-serif;">
    <div style="max-width:540px; margin:40px auto; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 8px 24px rgba(0,0,0,0.08);">
      
      <!-- Header -->
      <div style="background:#0aefff; padding:20px 30px; text-align:center;">
        <h1 style="margin:0; font-size:22px; font-weight:700; color:#ffffff;">OriginalLinks Verification</h1>
      </div>
      
      <!-- Body -->
      <div style="padding:30px 30px 20px;">
        <h2 style="color:#1c1c1c; font-size:20px; margin-top:0;">🔐 Verify Your Email</h2>
        <p style="color:#555; font-size:15px; margin:10px 0 24px;">
          To continue, please enter the following verification code. This helps us keep your account secure.
        </p>

        <div style="
          font-size:40px;
          font-weight:800;
          color:#0aefff;
          background:#f2fafe;
          text-align:center;
          padding:18px 0;
          border-radius:8px;
          letter-spacing:4px;
          user-select:all;
        ">
          {code}
        </div>

        <p style="font-size:14px; color:#666; margin:24px 0 10px;">
          This code will expire in <strong>5 minutes</strong>. If you did not request this code, no further action is needed.
        </p>
      </div>
      
      <!-- Footer -->
      <div style="padding:20px 30px; background:#fafafa; text-align:center; border-top:1px solid #eee;">
        <p style="margin:0; font-size:12px; color:#999;">Need help? Contact our support team at support@originallinks.com</p>
        <p style="margin:6px 0 0; font-size:11px; color:#bbb;">© 2025 OriginalLinks Security Team</p>
      </div>

    </div>
  </body>
</html>

    """

    try:
        msg = MIMEText(html, "html")
        msg["Subject"] = "Please Confirm Your Email Address to Continue and Unlock a Personalized Experience"
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
