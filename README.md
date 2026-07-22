# National Referral Calculator

A Streamlit web application for residential and commercial referral packages,
equipment additions and removals, approved MMR selections, customer options,
activation amounts, and automatic commission-point calculations.

## Repository files

- `app.py` — complete application and calculation logic
- `requirements.txt` — Python dependencies
- `render.yaml` — Render Blueprint configuration
- `.python-version` — Python version used by Render
- `.streamlit/config.toml` — Streamlit server defaults

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Upload to GitHub

From the project folder:

```bash
git init
git add .
git commit -m "Create national referral calculator"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

## Deploy to Render with Blueprint

1. Push all repository files to GitHub.
2. Sign in to Render.
3. Select **New +** and then **Blueprint**.
4. Connect the GitHub repository.
5. Render reads `render.yaml`.
6. Approve the service and deploy.

## Deploy manually as a Web Service

Use these values:

- Runtime: `Python`
- Build command: `pip install -r requirements.txt`
- Start command:
  `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true --browser.gatherUsageStats false`
- Health check path: `/_stcore/health`

Do not use `localhost` or a fixed port on Render. The app must listen on
`0.0.0.0` and Render's `$PORT`.

## Responsive design

The interface automatically adapts for:

- Desktop and laptop screens
- Tablets in portrait or landscape
- Mobile phones

Metric cards wrap automatically, multi-column forms stack on smaller screens,
tabs can scroll horizontally, controls use touch-friendly sizing, and tables
remain inside the viewport with horizontal scrolling when needed.
