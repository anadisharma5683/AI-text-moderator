# Deploying Chat Toxicity Moderator on Vercel

This guide explains how to deploy the Chat Toxicity Moderator application on Vercel with minimal configuration to avoid memory issues.

## 🚀 Quick Deployment

### Prerequisites
- A free [Vercel account](https://vercel.com/signup)
- [Vercel CLI](https://vercel.com/cli) installed (optional)

### Steps

1. **Prepare your repository**
   - Make sure you have this repository ready with all files
   - The `vercel.json` configuration is already included with minimal settings
   - The `api/moderate.py` file contains the serverless function with lightweight detection

2. **Deploy via Vercel Dashboard**
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your GitHub repository
   - Vercel will automatically detect the configuration
   - Click "Deploy"

3. **Deploy via CLI** (Alternative)
   ```bash
   # Install Vercel CLI
   npm i -g vercel
   
   # Navigate to project directory
   cd Chat-Toxicity-Moderator
   
   # Deploy
   vercel
   ```

## ⚙️ Environment Variables (Optional)

For enhanced functionality, add these environment variables in your Vercel project settings:

- `GROQ_API_KEY`: Your GROQ API key for improved rephrasing quality

To add environment variables:
1. Go to your project in the Vercel dashboard
2. Go to Settings → Environment Variables
3. Add the variables listed above

## 📁 Project Structure for Vercel

```
├── api/
│   └── moderate.py         # Vercel serverless function
├── public/
│   ├── index.html          # Main interface
│   ├── sender.html         # Sender view
│   ├── receiver.html       # Receiver view
│   ├── moderator.html      # Moderation dashboard
│   └── demo.html           # Demo instructions
├── requirements.txt        # Minimal Python dependencies
├── vercel.json             # Vercel configuration
└── README.md              # Project documentation
```

## 🌐 Accessing Your Deployed Application

After deployment, your application will be available at:
- **Main Interface**: `https://your-project-name.vercel.app/`
- **Sender View**: `https://your-project-name.vercel.app/sender.html`
- **Receiver View**: `https://your-project-name.vercel.app/receiver.html`
- **Moderation Dashboard**: `https://your-project-name.vercel.app/moderator.html`

## 🔧 API Endpoints

- `POST /api/moderate` - Moderate a message
- `GET /api/moderate` - Health check

Example API call:
```javascript
const response = await fetch('/api/moderate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ text: "Your message here" })
});
const result = await response.json();
```

## 🛠️ How It Works

The Vercel deployment uses:
- **Static hosting** for HTML files in the `public` directory
- **Serverless functions** for the moderation API
- **Minimal dependencies** to avoid memory issues during build
- **Keyword-based toxicity detection** for Vercel compatibility
- **Optional GROQ API** for enhanced rephrasing

## ⚠️ Important Notes

1. **Memory Optimization**: The project has been optimized to avoid heavy AI dependencies (PyTorch, Transformers, Detoxify) that cause memory issues during Vercel build.

2. **Minimal Dependencies**: Only essential packages (fastapi, uvicorn, openai, jinja2, groq, mangum) are included to ensure successful build.

3. **Keyword-based Detection**: Uses simple keyword matching instead of ML models for toxicity detection, which works efficiently within Vercel's constraints.

4. **API Keys**: When you provide a GROQ API key, the application will use more sophisticated rephrasing functionality.

5. **Performance**: This configuration ensures successful deployment on Vercel while maintaining core functionality.

## 📞 Support

If you encounter issues:
1. Check the Vercel deployment logs in your dashboard
2. Verify environment variables are properly set
3. Review the application in the browser console for any frontend errors

## 🔄 Updating Your Deployment

After making changes:
1. Push updates to your GitHub repository
2. Vercel will automatically redeploy
3. Or manually trigger a deployment from your dashboard