# VegiBulk - Vegetable Marketplace Backend

A Flask-based backend API for a Ghanaian vegetable marketplace platform.

## Deployment on Render

### Setup Steps

1. **Create a Render account** at https://render.com

2. **Set Environment Variables** in Render Dashboard:
   - Go to your project → Settings → Environment
   - Add the following variables:
     ```
     FLASK_ENV=production
     SECRET_KEY=<generate-a-secure-random-key>
     ALLOWED_ORIGINS=https://your-frontend-domain.com
     DATABASE_PATH=/var/data/vegibulk.db
     ```

3. **Deploy from GitHub**:
   - Push your code to GitHub
   - In Render, select "New Web Service"
   - Connect your GitHub repo
   - Configure:
     - **Runtime**: Python
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn app:app`
     - **Instance Type**: Free (or Starter)

### Important Notes

- **Persistent Storage**: Render provides `/var/data` directory for persistent storage. The database will be stored there.
- **Cold Starts**: Free tier instances may experience cold starts (takes ~30 seconds to spin up after inactivity)
- **Database**: Currently uses SQLite. For production apps with heavy load, consider migrating to PostgreSQL (Render offers this)

### Generate a Secure SECRET_KEY

Run this in your terminal:
```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Copy the output and add it to Render environment variables.

### Environment Variables Reference

| Variable | Value | Purpose |
|----------|-------|---------|
| `FLASK_ENV` | `production` | Sets Flask to production mode |
| `SECRET_KEY` | Random string | Session encryption key (required!) |
| `ALLOWED_ORIGINS` | Domain URL | Frontend domain for CORS |
| `DATABASE_PATH` | `/var/data/vegibulk.db` | Persistent database location |

### Health Check

Once deployed, verify it's working:
```bash
curl https://your-render-url.onrender.com/api/test
```

Expected response:
```json
{"message":"Frontend connected to backend successfully"}
```

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file:
```bash
cp .env.example .env
```

3. Run the app:
```bash
python app.py
```

The app will start on `http://localhost:5000`

## Production Checklist

- [ ] Change `SECRET_KEY` to a secure random value
- [ ] Set `ALLOWED_ORIGINS` to your frontend domain
- [ ] Set `FLASK_ENV=production`
- [ ] Test all API endpoints before going live
- [ ] Plan database migration if scaling beyond SQLite
