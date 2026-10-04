"""إعدادات الاتصال الموحّدة بقاعدة البيانات — تُستخدم من جميع السكربتات."""
import os
from dotenv import load_dotenv
import psycopg2




def get_connection():
    """إنشاء اتصال PostgreSQL/PostGIS من متغيرات البيئة .env"""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "gis_map"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
