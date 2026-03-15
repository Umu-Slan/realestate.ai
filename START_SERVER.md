# تشغيل السيرفر - Real Estate AI Console

## المتطلبات

- Docker Desktop (للبحث النصي pgvector يحتاج المشروع PostgreSQL)
- Python مع البيئة الافتراضية

## الخطوات

### 1. تشغيل قاعدة البيانات

افتح الطرفية في مجلد المشروع وشغّل:

```powershell
docker compose up -d
```

انتظر حتى يصبح PostgreSQL جاهزاً (حوالي 10–20 ثانية).

### 2. تطبيق الترحيلات (مرة واحدة)

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

### 3. إنشاء حساب مدير (مرة واحدة)

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

### 4. تشغيل السيرفر

**الطريقة 1 – من الطرفية:**

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

**الطريقة 2 – ملف التشغيل:**

```powershell
.\run_server.bat
```

أو:

```powershell
.\run_server.ps1
```

### 5. فتح التطبيق

- **لوحة التحكم:** http://127.0.0.1:8000/console/
- **تسجيل الدخول:** http://127.0.0.1:8000/accounts/login/

استخدم بيانات `createsuperuser` للتسجيل.

---

## استكشاف الأخطاء

| المشكلة | الحل |
|---------|------|
| `ERR_CONNECTION_REFUSED` | تأكد أن السيرفر يعمل وأنك شغّلت `runserver` |
| `connection refused` للـ database | شغّل `docker compose up -d` وتأكد أن Docker Desktop يعمل |
| `python: command not found` | استخدم المسار الكامل: `.\.venv\Scripts\python.exe` |
