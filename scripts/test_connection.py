"""فحص سريع لاتصال قاعدة البيانات (محلي أو Supabase) — بدون نقل بيانات.
الاستخدام:  py scripts/test_connection.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_config import get_connection

url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
target = "Supabase (SUPABASE_DB_URL)" if url else f"محلي ({os.getenv('DB_HOST','localhost')}/{os.getenv('DB_NAME','gis_map')})"
print(f"🔎 الهدف: {target}")
try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT postgis_version(), current_database(), count(*) FROM information_schema.tables WHERE table_name='features'")
    v, db, has = cur.fetchone()
    print("✅ الاتصال ناجح | DB=" + db + " | جدول features موجود:", bool(has))
    if has:
        cur.execute("SELECT COUNT(*) FROM features"); print(f"   عدد المعالم: {cur.fetchone()[0]}")
    conn.close()
except Exception as e:
    msg = str(e)
    print(f"❌ فشل الاتصال: {msg[:300]}")
    if "ENOTFOUND" in msg or "timeout" in msg.lower():
        print("💡 غالباً مشكلة IPv4: في Supabase استخدم Connection string من تبويب Other → Session pooler.")
    if "password authentication failed" in msg:
        print("💡 تأكد أنك استبدلت [your-password] بكلمة المرور الحقيقية.")
    sys.exit(1)