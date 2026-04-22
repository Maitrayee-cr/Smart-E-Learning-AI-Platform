# AI-Powered Smart E-Learning Management System

## Project Overview

Smart E-Learning is a role-based LMS with separate workflows for Student, Instructor, and Admin.
It supports course publishing, enrollment, mock payment, quiz attempts, certificate generation, and an explainable AI recommendation layer.

Current certificate rule:
- Student must complete full course video progress (100%)
- Student must pass the course quiz

## Tech Stack

- Frontend: HTML5, CSS3, JavaScript, Bootstrap 5, Chart.js
- Backend: Python, Django
- Database: SQLite (development-ready, structure is RDBMS friendly)

## Key Features

### AI Features

- Personalized course recommendation engine using hybrid content-based and collaborative signals from learner interests, enrollment history, completion, and quiz performance
- AI learning insights on the student dashboard with milestone guidance and next-action suggestions
- AI course match scoring on course detail pages with explainable recommendation reasons
- AI chatbot tutor for topic explanation, doubt solving, course guidance, voice input, and LMS-aware student answers
- Smart quiz generator for instructors that auto-builds MCQs from lesson notes with answer keys and difficulty labels
- Student performance prediction with risk, average, or high-performing probability bands on the dashboard
- Learning path optimization with next-best lessons and weak-topic revision guidance
- AI video summarizer that produces lesson highlights and key topics from course notes and lesson metadata
- Simulated emotion detection from uploaded snapshots with engagement analytics for instructor dashboards
- Optional Hugging Face emotion model support for low-cost/free-tier engagement analysis when `HF_TOKEN` is configured
- AI analytics dashboards for instructor and admin views with charts for performance bands, engagement trends, popularity, and quiz success
- Plagiarism detection for submitted answer text with similarity score and matched report
- Personalized homepage recommendations for logged-in students
- Works without external API keys by using an on-platform scoring engine built from LMS data

### Student

- Register and login (username or email supported on login)
- Browse courses with search/filter/sort
- Add to wishlist and cart
- Receive AI-ranked course recommendations
- Mock payment checkout (UPI/Card/Net Banking/Wallet)
- Enroll and watch full course video
- Course quiz attempt and result tracking
- View AI learning insights and next-step suggestions
- Certificate generation after quiz pass
- Review and rating submission

### Instructor

- Instructor dashboard with analytics
- Course create/edit/delete
- Upload course thumbnail, background, and full video
- Student enrollment view by instructor courses

### Admin

- Manage users, categories, courses, enrollments, reviews, messages
- Django admin support (`/admin/` and `/super-admin/`)
- Platform statistics dashboard

## Setup Instructions (Windows)

1. Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies

```powershell
pip install -r requirements.txt
```

3. Apply migrations

```powershell
python manage.py migrate
```

4. Load demo data

```powershell
python manage.py seed_demo_data
```

5. Run server

```powershell
python manage.py runserver
```

Optional Hugging Face setup for emotion detection:

```bash
export HF_TOKEN="your_hugging_face_token"
export HUGGINGFACE_EMOTION_MODEL="dima806/facial_emotions_image_detection"
python manage.py runserver
```

Provider order is Hugging Face first, then the local simulated fallback.
The Hugging Face provider uses the current router endpoint: `https://router.huggingface.co/hf-inference/models/...`.

6. Open in browser

- Home: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`
- Alternate admin: `http://127.0.0.1:8000/super-admin/`

## Demo Credentials

### Admin

- Username: `platformadmin`
- Password: `Admin@123`

### Instructors

- `anita_shah` / `Pass@123`
- `rohan_patel` / `Pass@123`
- `meera_joshi` / `Pass@123`
- `rahul_verma` / `Pass@123`
- `priya_mehta` / `Pass@123`

### Students

- `aisha` / `12345`
- `rahul` / `12345`
- `sneha` / `12345`
- `arjun` / `12345`
- `priya` / `12345`
- `karan` / `12345`
- `neha` / `12345`
- `rohan_student` / `12345`

You can also login with student email IDs (example: `aisha@gmail.com`).

## Project Structure

```text
smart_lms/
  apps/
    accounts/
    core/
    courses/
    learning/
  smart_lms/
    settings.py
    urls.py
  templates/
  static/
  media/
  manage.py
```

## GitHub Resume Submission

This project is ready to share as a GitHub repository for resume or portfolio use.
Do not commit local secrets, local database files, virtual environments, generated static files, or uploaded media.

Recommended files to commit:

```bash
git add api apps smart_lms templates static manage.py requirements.txt README.md .gitignore .env.example
git commit -m "Prepare Django LMS project for GitHub"
git push -u origin main
```

Do not commit:

```text
.env
db.sqlite3
.venv/
.venv_mac/
media/
staticfiles/
.DS_Store
```

## Notes For Final Submission

- Keep at least 2-3 courses with real media for presentation screenshots.
- Run with fresh seeded data before viva.
- Highlight the AI recommendation engine, AI insights dashboard, and AI course match score during project demo.
- If you edit models in future, run:

```powershell
python manage.py makemigrations
python manage.py migrate
```

## Troubleshooting

### Login issue

- Reseed accounts:

```powershell
python manage.py seed_demo_data
```

### CSRF issue (403)

- Hard refresh page (`Ctrl + F5`)
- Clear site cookies for `127.0.0.1` if needed
- Reopen login page and submit again
