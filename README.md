# متجري - Real Shop

متجر إلكتروني بسيط مع لوحة تحكم وربط ديسكورد.

## التشغيل المحلي

```bash
python server.py
```

ثم افتح: http://localhost:8080

كلمة مرور لوحة التحكم من متغير البيئة ADMIN_PASSWORD (الافتراضي: admin123)

## النشر على Render

1. ارفع المشروع على GitHub
2. New → Web Service
3. Runtime: Python
4. Start Command: `python server.py`
5. أضف Environment Variables:

| Key | Value |
|-----|-------|
| DISCORD_CLIENT_ID | Client ID من Discord |
| DISCORD_CLIENT_SECRET | Client Secret من Discord |
| DISCORD_REDIRECT_URI | https://your-app.onrender.com/api/discord/callback |
| ADMIN_PASSWORD | كلمة سر قوية |

6. في Discord Developer Portal → OAuth2 → Redirects أضف نفس رابط الـ Redirect URI.

## ملاحظات

- قاعدة البيانات SQLite تُنشأ تلقائياً.
- على Render المجاني القاعدة تُحذف عند إعادة التشغيل (ephemeral disk).
- غيّر الـ Client Secret فوراً إذا كان مكشوفاً من قبل.
