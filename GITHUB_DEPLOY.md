# رفع المشروع على GitHub والنشر

دليل احترافي لرفع المشروع على GitHub ثم نشره على Railway / Render / Vercel.

---

## 1. المتطلبات

- [Git](https://git-scm.com/) مُثبَّت
- حساب [GitHub](https://github.com)
- (للمراجعة) مشروع مكتمل محلياً

---

## 2. رفع المشروع على GitHub

### الخطوة 1: إنشاء المستودع على GitHub

1. ادخل إلى [github.com](https://github.com) وادخل لحسابك
2. اضغط **New repository** (أو **Create a new repository**)
3. اختَر:
   - **Repository name**: `realestate-ai` (أو الاسم الذي تريده)
   - **Description**: `Egyptian Real Estate AI – Lead qualification, sales chat, support triage`
   - **Visibility**: Private أو Public حسب اختيارك
   - **لا تضع**: README أو .gitignore أو License (المشروع يحتوي عليها)
4. اضغط **Create repository**

### الخطوة 2: ربط المشروع المحلي ورفعه

افتح Terminal (PowerShell أو CMD) وَنفّذ:

```powershell
cd C:\Users\nageh\.cursor\projects\Realestate

# إضافة الريموت (استبدل YOUR_USERNAME و REPO_NAME بروابطك)
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# أو مع SSH:
# git remote add origin git@github.com:YOUR_USERNAME/REPO_NAME.git

# التحقق
git remote -v

# رفع الفرع الرئيسي
git push -u origin main
```

إذا كان اسم الفرع `master`:

```powershell
git branch -M main
git push -u origin main
```

### الخطوة 3: التحقق

- افتح صفحة المستودع على GitHub
- تأكد أن الملفات ظهرت
- تحقق من عدم وجود ملفات حساسة (مثل `.env` أو مفاتيح API)

---

## 3. نشر المشروع (Deployment)

### خيار أ: Railway (موصى به لتطبيقات Django)

1. ادخل إلى [railway.app](https://railway.app) واتصل بحساب GitHub
2. **New Project** → **Deploy from GitHub repo**
3. اختر المستودع `realestate-ai`
4. أضف **PostgreSQL** من القائمة (Add PostgreSQL)
5. عيّن متغيرات البيئة من **Variables**:
   - `SECRET_KEY` = قيمة سرية (مثلاً: `python -c "import secrets; print(secrets.token_urlsafe(50))"`)
   - `ALLOWED_HOSTS` = `*` أو نطاقك
   - `DATABASE_URL` = (يتم توليده تلقائياً عند إضافة PostgreSQL)
6. النشر يتم تلقائياً عند كل `git push`

### خيار ب: Render

1. ادخل إلى [render.com](https://render.com) واتصل بحساب GitHub
2. **New** → **Web Service**
3. اختر المستودع
4. إعدادات الـ Build:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn config.wsgi:application`
5. إضافة **PostgreSQL** من قسم Databases
6. إضافة **Environment Variables** كما في Railway

### خيار ج: Docker (VPS / سيرفر خاص)

```powershell
git clone https://github.com/YOUR_USERNAME/realestate-ai.git
cd realestate-ai
cp .env.production.example .env
# عدّل .env بالقيم الصحيحة
docker compose -f docker-compose.production.yml up -d
```

انظر `DEPLOYMENT.md` للتفاصيل الكاملة.

### خيار د: Vercel

- Vercel مناسب في الأساس لتطبيقات Frontend/Node.js
- لتشغيل Django على Vercel يُستخدَم عادةً:
  - Serverless Adapter (مثل `django-vercel` أو `vercel-python`)
  - أو فصل الـ Frontend (مثلاً React/Next.js) على Vercel، والـ API على Railway/Render
- انظر وثائق [Vercel Python](https://vercel.com/docs/runtimes#official-runtimes/python) للتفاصيل

---

## 4. Checklist قبل الرفع

- [ ] لا يوجد ملف `.env` في Git (مغيّر في `.gitignore`)
- [ ] لا توجد مفاتيح API أو كلمات سر مكتوبة في الكود
- [ ] `SECRET_KEY` يتم تعيينه عبر متغيرات البيئة فقط
- [ ] `.env.example` موجود وبدون قيم حقيقية
- [ ] الاختبارات تعمل: `python -m pytest`

---

## 5. أوامر مفيدة

```powershell
# التحقق من حالة Git
git status

# عرض آخر commit
git log -1 --oneline

# إضافة ملفات وتثبيتها (إذا لم تكن مرفوعة بعد)
git add .
git status
git commit -m "Add production config"

# الرفع
git push origin main
```

---

## 6. مراجع

- [DEPLOYMENT.md](DEPLOYMENT.md) – إعدادات النشر التفصيلية
- [docs/DOCKER_LOCAL.md](docs/DOCKER_LOCAL.md) – بيئة Docker المحلية
- [.env.example](.env.example) – قالب متغيرات البيئة
