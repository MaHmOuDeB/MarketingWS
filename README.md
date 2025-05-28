# 🚀 Marketing Content Generator

A powerful, user-friendly web application that helps marketing professionals and businesses quickly generate customized, high-quality marketing content across a variety of campaign types.

---

## 🎯 Features

- **Multi-Channel Campaigns**: Social Media, Email Marketing, PPC Ads, Content Marketing, Customer Retention, Seasonal Campaigns, Product Launches, Crisis Management.  
- **Tone & Style**: Choose from multiple writing tones (casual, professional, urgent, friendly, serious and bright).  
- **Platform Optimization**: Social media templates tailor output for LinkedIn, Twitter, or Facebook.  
- **Language Support**: Generate and translate content in **English**, **Spanish**, **French**, or **German**.  
- **Interactive Feedback Loop**: Provide iterative feedback to refine copy, with clear diff view.  
- **Easy Export**: Download final copy as a text file.  

---

## 🛠️ Tech Stack

- **Backend**: Python • Flask • OpenAI API  
- **Frontend**: Streamlit  
- **Containerization**: Docker & Docker Compose (optional)  

---

## 🌐 Live Demo

Try it out online:

- **UI**: [https://marketing-ui-209535852921.europe-west3.run.app](https://marketing-ui-209535852921.europe-west3.run.app)  
- **API**: `https://marketing-api-209535852921.europe-west3.run.app/generate`  

---

## 📦 Requirements

- **Python** 3.9+  
- **Docker** & **Docker Compose** (optional)  
- **OpenAI API Key**  

---

## 🚧 Installation

### 1. Clone the repository
```bash
git clone git@github.com:your-username/marketing-content-generator.git
cd marketing-content-generator

## 2. Configuration

Copy the example environment file and set your OpenAI key:

Copy `.env.example` to `.env` and then edit:

- `OPENAI_API_KEY=your-openai-api-key`

---

## 3. Backend: Flask API

1. Change into the `app` directory  
2. Create and activate a Python venv  
3. Install dependencies  
4. Run the Flask server on port 5000  

After this, your API will be available at `http://localhost:5000`

---

## 4. Frontend: Streamlit UI

1. Change into the `ui` directory  
2. Create and activate a Python venv  
3. Install dependencies  
4. Launch the Streamlit app  

The UI will be accessible at `http://localhost:8501`

---

## 5. Docker Compose (alternative)

If you prefer containerization:

Run `docker compose up --build` from the project root, then access the UI at `http://localhost:8501`

---

## 📝 Usage

1. Select **Campaign Type** and **Tone**  
2. (If Social Media) choose **Platform**  
3. Enter your **Topic** (extended text area)  
4. Optionally specify an **Audience**  
5. Add any **Additional System Prompt** for custom instructions  
6. Click **Generate** to produce initial copy  
7. Provide **Feedback** and click **Improve** to iteratively refine  
8. View the **Latest Improvement** diff and **Download** the final text  
9. Change **Language** at any time to translate your refined copy 

```

This README was formatted with the assistance of AI for clarity and efficiency.
