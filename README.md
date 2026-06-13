# Agentic AI Job Application Bot

An intelligent, end-to-end automated pipeline that searches for job listings, ranks them using LLMs, optimizes resumes/cover letters for high-match compatibility, interacts with the user via Telegram for feedback, and automatically applies to qualified positions.

---

## Features

- **Dynamic Role Request**: Queries the user via Telegram for target roles (e.g., "Generative AI Engineer").
- **Resume Parsing**: Automatically extracts experience, skills, and projects from a PDF resume using PyMuPDF and Llama-3 (via NVIDIA API).
- **Automated Job Search**: Uses Playwright to query job sites (like Naukri) and collect job details.
- **ATS Match Scoring**: Analyzes job descriptions against the candidate's profile to compute compatibility scores.
- **Human-in-the-Loop Feedback**: Sends lists of missing skills to the user's Telegram. The bot waits for the user's decision on which skills to incorporate or skip before generating the final resumes.
- **Tailored Resume Generation**: Dynamically formats and compiles customized LaTeX resumes and PDFs using a MiKTeX/pdflatex integration.
- **Tailored Cover Letter Generation**: Generates customized cover letters targeting the specific job description.
- **Automated Application**: Applies to jobs automatically using Playwright, leveraging saved session states.
- **Progress Tracking**: Maintains a CSV sheet (`outputs/applications.csv`) of application states and messages reports to the user's Telegram.

---

## Repository Structure

```text
├── data/                    # Base user resume (PDF)
├── scripts/                 # Core Python pipeline scripts
│   ├── run_pipeline.py      # Main pipeline orchestrator
│   ├── save_session.py      # Utility to save browser login state
│   ├── job_search.py        # Playwright job scraper
│   ├── match_jobs.py        # LLM compatibility ranker
│   ├── latex_generator.py   # PDF LaTeX compiler
│   └── ... (other steps)
├── templates/               # LaTeX resume class files (.cls) and template (.tex)
├── .env.example             # Configuration variables template
├── requirements.txt         # Project dependencies
└── README.md                # Project documentation
```

---

## Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/Dhruvsoni4125/Agentic-AI-Job-Application-Bot.git
cd Agentic-AI-Job-Application-Bot
```

### 2. Configure Virtual Environment & Dependencies
Create a virtual environment and install the required Python libraries:
```bash
python -m venv venv
venv\Scripts\activate      # On Windows
source venv/bin/activate   # On Linux/macOS

pip install -r requirements.txt
playwright install
```

### 3. Install LaTeX Compiler (Optional for Resume PDFs)
To enable automated PDF compilation, ensure `pdflatex` is installed on your path:
- **Windows**: Install [MiKTeX](https://miktex.org/).
- **macOS**: Install MacTeX.
- **Linux**: Install TeX Live (`sudo apt-get install texlive-latex-extra`).

### 4. Set Up Environment Variables
Copy `.env.example` to `.env` and fill in your credentials:
```bash
copy .env.example .env
```
Inside `.env`:
- `NVIDIA_API_KEY`: API key for accessing NVIDIA's LLM endpoint.
- `TELEGRAM_BOT_TOKEN`: The token of your Telegram bot.
- `TELEGRAM_CHAT_ID`: Your Telegram Chat ID.

---

## Usage Workflow

### Step 1: Save Login Session
To perform automated job applications, log in manually once and save your cookies:
```bash
python scripts/save_session.py
```
This opens a browser window. Log in to your target job board (e.g., Naukri) and close the browser. A `naukri_session.json` file will be created to preserve your login session.

### Step 2: Prepare Base Resume
Place your current master resume in the `data/` folder named as `Dhruv_Resume.pdf`.

### Step 3: Run the Orchestrator Pipeline
Run the end-to-end automation:
```bash
python scripts/run_pipeline.py
```

---

## License

This project is licensed under the MIT License.
