"""Test SMTP – spusťte: python test_mail.py vas@email.cz"""
import os
import sys

# Načíst .env – ze složky skriptu nebo z CWD
try:
    from dotenv import load_dotenv
    from pathlib import Path
    env_path = Path(__file__).resolve().parent / ".env"
    ok = load_dotenv(env_path)
    if not ok:
        load_dotenv()  # fallback: CWD
except ImportError:
    pass

def main():
    to = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MAIL_FROM", "test@test.cz")
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    passwd = os.environ.get("SMTP_PASS")
    port = int(os.environ.get("SMTP_PORT", "587"))
    from_addr = os.environ.get("MAIL_FROM")
    
    print("Kontrola konfigurace:")
    print(f"  SMTP_HOST: {host}")
    print(f"  SMTP_PORT: {port}")
    print(f"  SMTP_USER: {user}")
    print(f"  MAIL_FROM: {from_addr}")
    print(f"  SMTP_PASS: {'***' if passwd else '(chybí!)'}")
    print()
    
    if not all([host, from_addr, user, passwd]):
        print("CHYBA: Chybí SMTP_HOST, MAIL_FROM, SMTP_USER nebo SMTP_PASS v .env")
        sys.exit(1)
    
    print(f"Odesílám testovací mail na {to}...")
    import smtplib
    from email.mime.text import MIMEText
    
    msg = MIMEText("Test – SMTP funguje.", "plain", "utf-8")
    msg["Subject"] = "Test – Vaping směnovač"
    msg["From"] = from_addr
    msg["To"] = to
    
    try:
        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            smtp.login(user, passwd)
            smtp.sendmail(from_addr, to, msg.as_string())
        print("OK – mail by měl dorazit (zkontroluj spam).")
    except Exception as e:
        print(f"CHYBA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
