# إعداد Vercel

## متغيرات البيئة المطلوبة

في Vercel Dashboard → Project → Settings → Environment Variables أضف:

| المتغير | الوصف | مثال |
|---------|-------|------|
| `SECRET_KEY` | مفتاح Django السري | `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `ALLOWED_HOSTS` | (اختياري) Vercel يضيف `.vercel.app` تلقائياً | `realestateai-peach.vercel.app,.vercel.app` |
| `DATABASE_URL` | رابط PostgreSQL | `postgresql://user:pass@host:5432/dbname` |

**ملاحظة:** Vercel لا يوفر PostgreSQL افتراضياً. استخدم:
- [Vercel Postgres](https://vercel.com/docs/storage/vercel-postgres) أو
- قاعدة بيانات خارجية (Railway، Supabase، إلخ)

## الروابط بعد النشر

- الصفحة الرئيسية: `https://your-project.vercel.app/` ← تحويل إلى الـ demo
- Demo Chat: `https://your-project.vercel.app/api/engines/demo/`
- Health: `https://your-project.vercel.app/health/`
