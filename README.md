# Kick Chat Webhook Monitor

Monitor Kick.com chat messages for $beef detection using official webhooks.

## Quick Deploy Options

### 1. Railway (Recommended - Free)
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Click "Deploy from GitHub repo"
4. Select this repository
5. Set environment variables:
   - `KICK_CLIENT_ID`: 01K49YM1DQK8CMAF1MNRQ6Z781
   - `KICK_CLIENT_SECRET`: 7b67c1efe2608c5050dbbe8ab8267444bbf6ac871ab4ebafe7cdbd78a6b4188f
   - `KICK_WEBHOOK_SECRET`: 285010f69a3dedf7337e584f01a9045e496fe122d9c19e74710c8c0870253882
6. Deploy!

### 2. Render (Free)
1. Go to [render.com](https://render.com)
2. Connect GitHub account
3. Create new Web Service
4. Select this repo
5. Set environment variables (same as above)
6. Deploy!

### 3. Heroku
1. Go to [heroku.com](https://heroku.com)
2. Create new app
3. Connect GitHub repo
4. Set Config Vars (environment variables)
5. Deploy!

## Setup After Deployment

1. **Get your deployed URL** (like `https://your-app.railway.app`)
2. **Go to Kick Developer Settings**
3. **Set webhook URL** to: `https://your-app.railway.app/webhook`
4. **Enable webhook events**
5. **Test by typing in kick.com/sam chat!**

## Dashboard

Visit your deployed URL to see:
- Real-time message count
- All received webhooks
- $beef detection counter
- Setup instructions

## Local Development

```bash
pip install -r requirements.txt
python app.py
```

Visit http://localhost:5000 for dashboard.