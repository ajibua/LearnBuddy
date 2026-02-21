# LearnBuddy Deployment Guide

## Deployment Architecture
- **Platform**: Railway
- **Domain**: learnbuddy.com (via Google Domains)
- **Database**: SQLite (can upgrade to PostgreSQL later)
- **Web Server**: Gunicorn + WhiteNoise
- **Static Files**: WhiteNoise CDN serving

## Step 1: Prepare Git Repository

First, ensure your code is in a Git repository:

```bash
cd c:\Users\HomePC\Desktop\LearnBuddy
git init
git add .
git commit -m "Initial commit: LearnBuddy application"
```

Push to GitHub (required for Railway):
```bash
git remote add origin https://github.com/ajibua/LearnBuddy.git
git push -u origin main
```

## Step 2: Deploy to Railway

### Option A: Railway CLI (Fastest)
1. Install Railway CLI: https://docs.railway.app/develop/cli
2. Login to Railway:
```bash
railway login
```

3. Initialize and deploy:
```bash
railway init
railway up
```

### Option B: Railway Dashboard (Easiest)
1. Go to https://railway.app
2. Sign up with GitHub
3. Click "New Project" → "Deploy from GitHub"
4. Select the LearnBuddy repository
5. Railway will auto-detect it's a Python/Django app

## Step 3: Configure Environment Variables on Railway

In Railway Dashboard, go to your project and add these variables:

```
SECRET_KEY = <generate a new secure key>
DEBUG = False
DOMAIN = learnbuddy.com
GOOGLE_API_KEY = <paste your API key>
```

### Generate a new SECRET_KEY:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Step 4: Database Setup on Railway

After deployment, run migrations:

```bash
railway run python manage.py migrate
railway run python manage.py createsuperuser
```

This creates:
- Database tables
- Admin user for http://yourapp.railway.app/admin

## Step 5: Register Domain on Google Domains

1. Go to https://domains.google
2. Search for "learnbuddy.com"
3. Add to cart and complete purchase
4. In Google Domains settings, go to **DNS**

## Step 6: Connect Domain to Railway

1. In Railway Dashboard, go to your project settings
2. Find "Domains" section
3. Click "Add Domain"
4. Enter: `learnbuddy.com`
5. Railway will show you the nameserver addresses

Alternative: Add CNAME record in Google Domains:

1. In Google Domains DNS settings
2. Find "Custom records" section  
3. Add CNAME record:
   - Name: `@` (for root) or `www`
   - Type: `CNAME`
   - Data: Your Railway domain (e.g., `yourapp.railway.app`)

Wait 24-48 hours for DNS propagation.

## Step 7: Verify Deployment

1. Visit your Railway URL: https://yourapp.railway.app
2. Verify all features work:
   - Login/Signup
   - Chat functionality
   - File upload
   - Web search
3. Once domain is live, visit https://learnbuddy.com
4. Access admin at https://learnbuddy.com/admin

## Step 8: Enable HTTPS (Automatic with Railway)

Railway automatically provides free SSL/TLS certificates. Already configured in settings.py with:
- `SECURE_SSL_REDIRECT = True`
- `SESSION_COOKIE_SECURE = True`

## Troubleshooting

### 502 Bad Gateway Error
- Check Railway logs: `railway logs`
- Verify migrations ran: `railway run python manage.py migrate`
- Check SECRET_KEY is set in environment variables

### Static files not loading (CSS/JS)
- Collect static files: `railway run python manage.py collectstatic --noinput`
- WhiteNoise should serve them automatically

### Login not working
- Ensure database migrations are complete
- Check if users table exists: `railway run python manage.py shell`
- Create superuser: `railway run python manage.py createsuperuser`

### Domain not connecting
- Wait for DNS propagation (can take 24-48 hours)
- Verify CNAME records in Google Domains
- Check Railway custom domain settings

## Performance Optimization (Future)

1. **Upgrade to PostgreSQL** on Railway
2. **Add Redis cache** for sessions and search results caching
3. **Enable CloudFront CDN** for static files and media
4. **Upgrade dyno size** if needed for heavy processing

## Monitoring & Maintenance

### View Logs
```bash
railway logs --follow
```

### Monitor Performance
- Railway Dashboard shows CPU, memory, and request metrics
- Set up email alerts for downtime

### Backup Database
Railway automatically backs up SQLite daily. For critical data:
```bash
railway run python manage.py dumpdata > backup.json
```

## Cost Estimation

- **Railway**: ~$5-10/month (free tier available with limits)
- **Google Domains**: ~$12/year
- **Total**: ~$60-130/year

## After Deployment Checklist

- [ ] App deployed and running on Railway
- [ ] Domain registered on Google Domains
- [ ] Domain connected to Railway
- [ ] HTTPS working (green lock)
- [ ] Migrations completed
- [ ] Admin user created
- [ ] GOOGLE_API_KEY configured
- [ ] Tests run on live URL
- [ ] Backup plan in place

## Rollback If Needed

To revert to previous version on Railway:
1. Go to Railway Dashboard
2. Click "Deployments"
3. Select previous working deployment
4. Click "Redeploy"

---

**Next Steps**: Once deployed, monitor the logs and test all features thoroughly before sharing with users!
