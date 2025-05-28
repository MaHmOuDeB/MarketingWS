🚀 Marketing Content Generator

This project is a powerful and user-friendly web application designed to help marketing professionals and businesses quickly generate customized, high-quality marketing content across various campaign types.

🎯 Features
	•	Generate content for different marketing campaigns:
	•	Social Media
	•	Email Marketing
	•	PPC Ads
	•	Content Marketing
	•	Customer Retention
	•	Seasonal Campaigns
	•	Product Launches
	•	Crisis Management
	•	Supports multiple tones and languages (English, Spanish, French, German).
	•	User feedback integration for iterative improvements.
	•	Easy translation and content improvements directly from the UI.

🛠️ Tech Stack
	•	Backend: Python, Flask, OpenAI API
	•	Frontend: Streamlit
	•	Containerization: Docker Compose

🌐 Live Demo

Experience the live deployed application here:
	•	UI: https://marketing-ui-209535852921.europe-west3.run.app
	•	API: https://marketing-api-209535852921.europe-west3.run.app/generate (for programmatic access)

📦 Requirements
	•	Python 3.9+
	•	Docker and Docker Compose (optional)
	•	OpenAI API Key

🚧 Installation
	1.	Clone the repo

git clone git@github.com:your-username/marketing-content-generator.git
cd marketing-content-generator


	2.	🔐 Configuration
Copy the example environment file and add your OpenAI key:

cp .env.example .env

Edit .env and set:

OPENAI_API_KEY=your-openai-api-key


	3.	💻 Backend: Flask API

cd app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run --port 5000

API is now live at: http://localhost:5000

	4.	🖥️ Frontend: Streamlit UI
Open a new terminal window:

cd ui
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_ui.py

UI is accessible at: http://localhost:8501

🐳 Docker Compose (Alternative setup)

To run the app in Docker containers:

Docker compose up --build

The app will be available at: http://localhost:8501

📝 Usage
	1.	Fill out the necessary fields in the sidebar.
	2.	Click Generate to create your content.
	3.	Use the Feedback section to request improvements.
	4.	Select a different Language to translate your generated content.
	5.	Download generated content directly from the UI.
