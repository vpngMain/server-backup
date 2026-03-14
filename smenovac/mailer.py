"""E-mailové notifikace. Konfigurace přes env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, MAIL_FROM, APP_URL."""
import os
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr


def _is_configured():
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("MAIL_FROM"))


def _email_wrapper(inner_html: str) -> str:
    """Obaluje obsah e-mailu do jednotné šablony s hlavičkou a patičkou."""
    app_url = (os.environ.get("APP_URL") or "").strip().rstrip("/")
    header_link = f'<a href="{app_url}" style="color:#fff;text-decoration:none;font-weight:700">Směnovač</a>' if app_url else "Směnovač"
    return f"""
<!DOCTYPE html>
<html lang="cs">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Směnovač</title>
</head>
<body style="margin:0;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:16px;line-height:1.6;color:#374151;background:#f3f4f6;padding:1rem 0">
  <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08)">
    <div style="background:#2563eb;color:#fff;padding:1rem 1.25rem;font-weight:700;font-size:1.125rem">
      📋 {header_link}
    </div>
    <div style="padding:1.5rem 1.25rem">
      {inner_html}
    </div>
    <div style="padding:1rem 1.25rem;background:#f9fafb;font-size:0.875rem;color:#6b7280;border-top:1px solid #e5e7eb">
      Tento e-mail přišel z aplikace Vaping směnovač. {f'<a href="{app_url}" style="color:#2563eb;text-decoration:none">Otevřít aplikaci</a>' if app_url else ''}
    </div>
  </div>
</body>
</html>
"""


def send_mail(to_email: str, subject: str, body_html: str, body_text: str = None):
    """Odešle e-mail. Pokud SMTP není nakonfigurováno, tiše nic neudělá."""
    if not _is_configured():
        if os.environ.get("MAIL_DEBUG") == "1":
            print("[mailer] Mail neodeslán – chybí SMTP_HOST nebo MAIL_FROM v .env", file=sys.stderr)
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr(("Vaping směnovač", os.environ.get("MAIL_FROM")))
        msg["To"] = to_email

        wrapped_html = _email_wrapper(body_html)
        msg.attach(MIMEText(body_text or _html_to_plain(body_html), "plain", "utf-8"))
        msg.attach(MIMEText(wrapped_html, "html", "utf-8"))

        host = os.environ.get("SMTP_HOST", "localhost")
        try:
            port = int(os.environ.get("SMTP_PORT", "587"))
        except (TypeError, ValueError):
            port = 587
        user = os.environ.get("SMTP_USER")
        password = os.environ.get("SMTP_PASS")
        use_tls = os.environ.get("SMTP_TLS", "1") == "1"

        with smtplib.SMTP(host, port) as smtp:
            if use_tls:
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(os.environ.get("MAIL_FROM"), to_email, msg.as_string())
    except Exception as e:
        print(f"[mailer] Chyba odeslání na {to_email}: {e}", file=sys.stderr)


def _html_to_plain(html: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", "", html)
    return re.sub(r"\s+", " ", text).strip()


def notify_admin_new_request(admin_email: str, employee_name: str, req_type: str, details: str):
    """Admin dostane mail o nové žádosti."""
    subject = f"Nová žádost: {employee_name} – {req_type}"
    body = f"""
    <p>Zaměstnanec <strong>{employee_name}</strong> odeslal novou žádost.</p>
    <p><strong>Typ:</strong> {req_type}</p>
    <p><strong>Detaily:</strong> {details}</p>
    <p>Přihlaste se do aplikace a žádost vyřízte.</p>
    """
    send_mail(admin_email, subject, body)


def notify_employee_request_resolved(employee_email: str, req_type: str, approved: bool):
    """Zaměstnanec dostane mail o vyřízení žádosti."""
    status = "schválena" if approved else "zamítnuta"
    subject = f"Žádost o {req_type} byla {status}"
    body = f"""
    <p>Vaše žádost o {req_type} byla <strong>{status}</strong>.</p>
    <p>Přihlaste se do aplikace pro více detailů.</p>
    """
    send_mail(employee_email, subject, body)


def notify_reset_password_link(to_email: str, reset_url: str):
    """Odeslání odkazu pro reset hesla (zapomenuté heslo)."""
    subject = "Reset hesla – Vaping směnovač"
    body = f"""
    <p>Obdrželi jsme žádost o reset hesla pro váš účet.</p>
    <p>Pro nastavení nového hesla klikněte na odkaz:</p>
    <p><a href="{reset_url}" style="display:inline-block;padding:0.75rem 1.5rem;background:#2563eb;color:white;text-decoration:none;border-radius:0.5rem;font-weight:600">Resetovat heslo</a></p>
    <p>Nebo zkopírujte odkaz do prohlížeče:</p>
    <p style="word-break:break-all;font-size:0.875rem;color:#6b7280">{reset_url}</p>
    <p>Odkaz platí 1 hodinu.</p>
    <p>Pokud jste o reset nežádali, tento e-mail ignorujte.</p>
    """
    send_mail(to_email, subject, body)


def notify_set_password_link(to_email: str, name: str, set_password_url: str):
    """Odeslání odkazu pro vytvoření hesla po schválení registrace."""
    subject = "Vytvoření hesla – Vaping směnovač"
    body = f"""
    <p>Ahoj {name},</p>
    <p>Vaše registrace byla schválena. Pro vytvoření hesla a aktivaci účtu klikněte na odkaz:</p>
    <p><a href="{set_password_url}" style="display:inline-block;padding:0.75rem 1.5rem;background:#2563eb;color:white;text-decoration:none;border-radius:0.5rem;font-weight:600">Vytvořit heslo</a></p>
    <p>Nebo zkopírujte odkaz do prohlížeče:</p>
    <p style="word-break:break-all;font-size:0.875rem;color:#6b7280">{set_password_url}</p>
    <p>Odkaz platí 7 dní.</p>
    <p>Pokud jste se neregistrovali, tento e-mail ignorujte.</p>
    """
    send_mail(to_email, subject, body)


def notify_employee_shift(employee_email: str, employee_name: str, date: str, start: str, end: str, is_new: bool):
    """Zaměstnanec dostane mail o změněné směně (ne při přidání – pouze při editaci)."""
    parts = str(date).split("-")
    date_fmt = f"{parts[2]}.{parts[1]}.{parts[0]}" if len(parts) == 3 else date
    subject = f"Směna změněna: {date_fmt} {start}–{end}"
    body = f"""
    <p>Ahoj {employee_name},</p>
    <p>Vaše směna byla upravena:</p>
    <p><strong>{date_fmt}</strong> od {start} do {end}</p>
    <p>Přihlaste se do aplikace pro detaily.</p>
    """
    send_mail(employee_email, subject, body)


def _fmt_date_for_email(d):
    parts = str(d).split("-")
    return f"{parts[2]}.{parts[1]}.{parts[0]}" if len(parts) == 3 else d


def notify_employee_schedule(employee_email: str, employee_name: str, shifts_html: str, from_date: str, to_date: str):
    """Zaměstnanec dostane mail s rozpisem směn (plán)."""
    from_fmt = _fmt_date_for_email(from_date)
    to_fmt = _fmt_date_for_email(to_date)
    subject = f"Rozpis směn {from_fmt} – {to_fmt}"
    body = f"""
    <p>Ahoj {employee_name},</p>
    <p>Připravili jsme pro vás rozpis směn na dané období:</p>
    {shifts_html}
    <p style="margin-top:1.5rem;padding:0.75rem;background:#fef3c7;border-radius:0.5rem;color:#92400e">
    <strong>Poznámka:</strong> Toto je pouze plán. Směny ještě mohou být změněny. Aktuální rozvrh najdete v aplikaci.
    </p>
    <p>Přihlaste se do aplikace pro nejaktuálnější informace.</p>
    """
    send_mail(employee_email, subject, body)
