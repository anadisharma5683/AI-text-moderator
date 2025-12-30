# Chat Toxicity Moderator - Ready for Deployment

This is a real-time chat application that detects and rephrases toxic messages using AI. The application is now prepared for deployment on various platforms including Vercel.

## 🚀 Deploy to Vercel

[![Deploy to Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/your-username/Chat-Toxicity-Moderator)

### One-Click Deployment

Click the button above to deploy directly to Vercel, or follow the manual steps below.

### Manual Deployment Steps

1. **Sign up for Vercel** at [vercel.com](https://vercel.com/signup)

2. **Clone or fork this repository**

3. **Deploy via Vercel CLI**:
   ```bash
   # Install Vercel CLI
   npm i -g vercel
   
   # Navigate to project directory
   cd Chat-Toxicity-Moderator
   
   # Deploy
   vercel --prod
   ```

4. **Or deploy via Vercel Dashboard**:
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your GitHub repository
   - Vercel will automatically detect the configuration
   - Click "Deploy"

## ⚙️ Environment Variables (Optional)

For enhanced functionality, add these environment variables in your Vercel project settings:

- `GROQ_API_KEY`: Your GROQ API key for improved rephrasing quality

## 🌐 Accessing Your Application

After deployment, your application will be available at:
- **Main Interface**: `https://your-project-name.vercel.app/`
- **Sender View**: `https://your-project-name.vercel.app/sender.html`
- **Receiver View**: `https://your-project-name.vercel.app/receiver.html`
- **Moderation Dashboard**: `https://your-project-name.vercel.app/moderator.html`

## 🏗️ Repository Structure

```
├── api/                    # Vercel API routes
│   └── moderate.py         # Moderation API endpoint
├── public/                 # Static frontend files
│   ├── index.html          # Main interface
│   ├── sender.html         # Sender view
│   ├── receiver.html       # Receiver view  
│   └── moderator.html      # Moderation dashboard
├── requirements.txt        # Python dependencies
├── vercel.json             # Vercel configuration
└── VERCEL_INSTRUCTIONS.md  # Detailed Vercel deployment guide
```

## 🛠️ Features

- **Real-time toxicity detection** using keyword-based analysis (optimized for Vercel)
- **Automatic message rephrasing** using GROQ API (when API key provided)
- **Clean, modern UI** with separate sender/receiver views
- **Works without API keys** using fallback logic

## 🔧 API Endpoints

- `POST /api/moderate` - Moderate a message
- `GET /` - Health check

Example API call:
```javascript
const response = await fetch('/api/moderate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ text: "Your message here" })
});
const result = await response.json();
```

## 📋 Prerequisites for Full ML Functionality

For the complete ML functionality with local models, consider using Render, Railway, or Docker deployment options instead of Vercel, as Vercel has limitations with large model loading and longer execution times.

## 📖 Detailed Deployment Guide

For more information about deployment options and alternatives, see [VERCEL_INSTRUCTIONS.md](./VERCEL_INSTRUCTIONS.md).