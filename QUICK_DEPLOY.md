# LearnBuddy - Quick Deployment Guide

## What You Need
- GitHub account (for code)
- Railway account (for hosting) - https://railway.app
- Google Domains account (for domain) - https://domains.google

## 🚀 Quick Deployment Steps (30 min)

### Step 1: Push Code to GitHub (5 min)
```bash
cd c:\Users\HomePC\Desktop\LearnBuddy
git init
git add .
git commit -m "Ready for deployment"
git remote add origin https://github.com/YOUR_USERNAME/LearnBuddy.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy to Railway (3 min)
1. Go to https://railway.app/dashboard
2. Click: **New Project** → **Deploy from GitHub repo**
3. Select **LearnBuddy**
4. Railway auto-builds and deploys!
5. Wait ~2-3 minutes for deployment
6. You get a free URL like: `yourapp-production.up.railway.app`

### Step 3: Set Environment Variables (2 min)
In Railway Dashboard:
1. Click your project
2. Go to **Variables**
3. Add these:

```
SECRET_KEY=<run: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=False
DOMAIN=learnbuddy.com
GOOGLE_API_KEY=<your API key>
```

### Step 4: Run Migrations (1 min)
Click **Deploy** → **Logs** → Run:
```bash
python manage.py migrate
python manage.py createsuperuser
```

### Step 5: Register Domain (5 min)
1. Go to https://domains.google
2. Search **learnbuddy.com**
3. Buy it (~$12/year)
4. Go to **DNS Settings**

### Step 6: Connect Domain (5 min)
**Option A - Via Railway DNS (easiest):**
1. In Railway: Click project → **Settings**
2. Scroll to **Domains**
3. Click **Add Custom Domain**
4. Enter: `learnbuddy.com`
5. Copy the Nameserver addresses
6. In Google Domains → **DNS** → **Custom nameservers**
7. Paste namservers
8. Wait 12-48 hours for DNS update

**Option B - Via CNAME (faster propagation):**
1. In Google Domains → **DNS** → **Custom records**
2. Add: Type: CNAME | Name: @ | Data: yourapp.railway.app
3. Wait 4-24 hours

### Step 7: Verify Deployment (2 min)
- Visit: https://yourapp.railway.app (instant)
- Visit: https://learnbuddy.com (after DNS propagates)
- Login with superuser credentials
- Test: Chat, Upload, Web Search
- Access: https://learnbuddy.com/admin

---

## Total Cost
- **Railway**: Free tier (~$5-10/month when you exceed free tier)
- **Google Domains**: ~$12/year  
- **Total**: Very affordable!

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Site shows error | Check Railway logs, verify migrations ran |
| Static files broken | Run `collectstatic` in Railway one-off |
| Domain not working | Wait for DNS (24-48h), check nameservers |
| Can't login | Ensure `createsuperuser` was run |

## After Deployment
- ✅ App is live with HTTPS
- ✅ Database auto-created
- ✅ Static files served by WhiteNoise
- ✅ Email admin@learnbuddy.com if issues

## Files Prepared for Deployment
- ✅ `Procfile` - tells Railway how to run
- ✅ `runtime.txt` - specifies Python 3.11
- ✅ `requirements.txt` - all dependencies with versions
- ✅ `.env.example` - template for environment variables
- ✅ `DEPLOYMENT.md` - detailed guide (this file + more)
- ✅ `settings.py` - configured for production

---

**Ready? Start with Step 1 above!** 🎓
