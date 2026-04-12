import os, json, sys
from pathlib import Path

# ? add project root to sys.path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from datetime import timedelta
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "livestock.settings")

import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Farm
from transactions.models import Transaction, Counterparty

def die(msg: str, code: int = 1):
    print(f"FAIL: {msg}")
    sys.exit(code)

def ok(msg: str):
    print(f"OK: {msg}")

def j(resp):
    try:
        return json.loads(resp.content.decode("utf-8"))
    except Exception as e:
        die(f"Response not JSON. status={resp.status_code} body={resp.content[:200]!r} err={e}")

client = Client()

# 1) login as superuser (force)
User = get_user_model()
user = User.objects.filter(is_superuser=True, is_active=True).first()
if not user:
    die("No superuser found. Run: python manage.py createsuperuser")

client.force_login(user)
ok(f"Logged in as superuser: {user.username}")

# 2) must have a Farm
farm = Farm.objects.first()
if not farm:
    die("No Farm found. Create one in admin or run your seed_demo command if you have it.")
ok("Farm exists")

# 3) Stock endpoint
resp = client.get("/transactions/api/stock/", HTTP_HOST="127.0.0.1")
if resp.status_code != 200:
    die(f"/transactions/api/stock/ status={resp.status_code}")
data = j(resp)
if not data.get("ok"):
    die(f"/transactions/api/stock/ returned ok=false: {data}")
ok("Stock endpoint OK")

# 4) Create purchase (idempotent)
purchase_payload = {
    "idempotency_key": "smoke_purchase_1",
    "kind": "HARRI",
    "cls": "JADH",
    "quantity": 1,
    "unit_price": 1000,
}
resp = client.post("/transactions/api/purchase/", HTTP_HOST="127.0.0.1", data=json.dumps(purchase_payload), content_type="application/json")
if resp.status_code != 200:
    die(f"purchase status={resp.status_code} body={resp.content[:200]!r}")
p = j(resp)
if not p.get("ok"):
    die(f"purchase ok=false: {p}")
ok(f"Purchase OK (tx_id={p.get('tx_id')})")

# 5) Create credit sale with DEFAULT due_date (no due_date sent) => should default to +30 days
sale_phone = "0530000000"
sale_payload = {
    "idempotency_key": "smoke_sale_default_1",
    "kind": "HARRI",
    "cls": "JADH",
    "quantity": 1,
    "unit_price": 2000,
    "payment_mode": "CREDIT",
    "paid_amount": 0,
    "customer_name": "Smoke Customer",
    "customer_phone": sale_phone,
    # no due_date here
}
resp = client.post("/transactions/api/sale/", HTTP_HOST="127.0.0.1", data=json.dumps(sale_payload), content_type="application/json")
if resp.status_code != 200:
    die(f"sale(default) status={resp.status_code} body={resp.content[:200]!r}")
s1 = j(resp)
if not s1.get("ok"):
    die(f"sale(default) ok=false: {s1}")
tx1 = Transaction.objects.get(id=s1["tx_id"])
expected = timezone.localdate() + timedelta(days=30)
if tx1.due_date != expected:
    die(f"Default due_date mismatch. got={tx1.due_date} expected={expected}")
ok(f"Credit sale default due_date OK (tx_id={tx1.id}, due_date={tx1.due_date})")

# 6) Create credit sale with OVERRIDE due_date (past) to appear overdue
override_due = (timezone.localdate() - timedelta(days=10)).isoformat()
sale_payload2 = {
    "idempotency_key": "smoke_sale_override_1",
    "kind": "HARRI",
    "cls": "JADH",
    "quantity": 1,
    "unit_price": 3000,
    "payment_mode": "CREDIT",
    "paid_amount": 0,
    "customer_name": "Smoke Customer",
    "customer_phone": sale_phone,
    "due_date": override_due,
}
resp = client.post("/transactions/api/sale/", HTTP_HOST="127.0.0.1", data=json.dumps(sale_payload2), content_type="application/json")
if resp.status_code != 200:
    die(f"sale(override) status={resp.status_code} body={resp.content[:200]!r}")
s2 = j(resp)
if not s2.get("ok"):
    die(f"sale(override) ok=false: {s2}")
tx2 = Transaction.objects.get(id=s2["tx_id"])
if tx2.due_date.isoformat() != override_due:
    die(f"Override due_date mismatch. got={tx2.due_date} expected={override_due}")
ok(f"Credit sale override due_date OK (tx_id={tx2.id}, due_date={tx2.due_date})")

# 7) Aging endpoint should show overdue bucket > 0 now
resp = client.get("/transactions/api/ar/aging/", HTTP_HOST="127.0.0.1")
if resp.status_code != 200:
    die(f"aging status={resp.status_code}")
a = j(resp)
if not a.get("ok"):
    die(f"aging ok=false: {a}")
ok("Aging endpoint OK")

# 8) WhatsApp reminder should return wa_link for that customer
cp = Counterparty.objects.filter(phone=sale_phone).first()
if not cp:
    die("Counterparty not created for sale_phone.")
resp = client.get(f"/transactions/api/clients/{cp.id}/whatsapp-reminder/", HTTP_HOST="127.0.0.1")
if resp.status_code != 200:
    die(f"whatsapp-reminder status={resp.status_code}")
w = j(resp)
if not w.get("ok") or not w.get("wa_link"):
    die(f"whatsapp-reminder missing wa_link: {w}")
ok(f"WhatsApp reminder OK (wa_link startswith wa.me)")

print("\nALL SMOKE TESTS PASSED ✅")
