# 🚀 Marketing Content Generator

This project is a powerful and user-friendly web application designed to help marketing professionals and businesses quickly generate customized, high-quality marketing content across various campaign types.

---

## 🎯 Features

* Generate content for different marketing campaigns:

  * Social Media
  * Email Marketing
  * PPC Ads
  * Content Marketing
  * Customer Retention
  * Seasonal Campaigns
  * Product Launches
  * Crisis Management

* Supports multiple tones and languages (English, Spanish, French, German).

* User feedback integration for iterative improvements.

* Easy translation and content improvements directly from the UI.

---

## 🛠️ Tech Stack

* **Backend**: Python, Flask, OpenAI API
* **Frontend**: Streamlit
* **Containerization**: Docker Compose

---

## 📦 Requirements

* Python 3.9+
* Docker and Docker Compose (optional for containerization)
* OpenAI API Key

---

## 🚧 Installation

### 1. Clone the repo

```bash
git clone git@github.com:your-username/marketing-content-generator.git
cd marketing-content-generator
```

### 2. 🔐 Configuration

Copy the example environment file and add your OpenAI key:

```bash
cp .env.example .env
```

Open `.env` and set your key:

```env
OPENAI_API_KEY=your-openai-api-key
```

> **Note:** `.env` is listed in `.gitignore` to avoid accidentally committing your API key.

---

### 3. 💻 Backend: Flask API

```bash
cd app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run --port 5000
```

API is now live at: `http://localhost:5000`

---

### 4. 🖥️ Frontend: Streamlit UI

Open a new terminal window:

```bash
cd ui
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_ui.py
```

UI is accessible at: `http://localhost:8501`

---

## 🐳 Docker Compose (Alternative setup)

To run the app in Docker containers:

```bash
docker compose up --build
```

The app will be available at: `http://localhost:8501`

---

## 📝 Usage

* Fill out the necessary fields in the sidebar.
* Click **Generate** to create your content.
* Use the **Feedback** section to request improvements.
* Select a different **Language** to translate your generated content.
* Download generated content directly from the UI.
