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
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Email Verification</title>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=Inter:wght@400;600;800&display=swap" rel="stylesheet" />
  </head>
  <body style="margin:0; padding:0; background:#f0f2f7; font-family:'Inter', 'DM Sans', sans-serif;">
    <div style="max-width:600px; margin:40px auto; background:#fff; border-radius:16px; overflow:hidden; box-shadow:0 10px 40px rgba(0,0,0,0.08);">
      
      <!-- Header -->
      <div style="background:linear-gradient(90deg, #00e3ff, #007eff); padding:24px 32px; text-align:center;">
        <h1 style="margin:0; font-size:24px; font-weight:700; color:#ffffff; letter-spacing:-0.5px;">
          Confirm Your Email to Unlock Personalization
        </h1>
      </div>

      <!-- Body -->
      <div style="padding:36px 32px 24px;">
        <h2 style="color:#1a1a1a; font-size:20px; font-weight:600; margin:0 0 12px;">Your Verification Code</h2>
        <p style="color:#555d66; font-size:15px; line-height:1.6; margin:0 0 28px;">
          To continue, please enter the code below. This helps us verify your identity and enhance your personalized experience.
        </p>

        <div style="
          font-size:36px;
          font-weight:800;
          color:#007eff;
          background:#eef7ff;
          text-align:center;
          padding:20px;
          border-radius:10px;
          letter-spacing:6px;
          user-select:all;
          word-break:break-all;
        ">
          {code}
        </div>

        <p style="font-size:14px; color:#7b7b7b; margin:28px 0 12px;">
          This code will expire in <strong>5 minutes</strong>. If you didn’t request it, just ignore this message.
        </p>
      </div>

      <!-- Footer -->
      <div style="padding:24px 32px; background:#f9f9f9; text-align:center; border-top:1px solid #e4e4e4;">
        <p style="margin:0; font-size:13px; color:#888;">Need help? Reach out at <a href="mailto:Orignallinks@gmail.com" style="color:#007eff; text-decoration:none;">support@originallinks.com</a></p>
        <p style="margin:6px 0 0; font-size:12px; color:#aaa;">© 2025 OriginalLinks — All rights reserved.</p>
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
