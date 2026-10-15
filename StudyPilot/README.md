# StudyPilot — INNOHACKS 2.0 MVP

**Problem statement:** EdTech — “What to Study Next” Recommender.

StudyPilot turns quiz performance into an explainable, personalised study plan. The student selects a class/level from Class 1 through Class 12 or Undergraduate, chooses a subject, completes a short quiz, reviews topic scores, and gets a time-bounded revision plan. Account profiles and quiz history are saved in SQLite, so students can sign in again and continue.

## Features in this MVP

- Login, account creation, logout, and a one-click demo workspace.
- Passwords stored as Werkzeug password hashes, not plain text.
- Saved user profile: name, email, class/level and preferred subject.
- Curriculum bands and subject options for primary, middle, secondary, senior-secondary and college stages.
- Six curated sample questions per subject/level set, grouped into topics.
- Topic-level scoring, an explainable weakness-priority formula, configurable 15–120 minute plan, focused retest and saved session history.
- Responsive interface with subtle motion; supports `prefers-reduced-motion`.

## Run locally (Windows)

1. Install Python 3.10+.
2. Extract the ZIP and double-click `run.bat`, or run:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python app.py
   ```

3. Open **http://127.0.0.1:5000** and click **Explore the demo workspace**.

### Demo account

- Email: `demo@studypilot.app`
- Password: `PilotDemo2026!`

No account setup is necessary for the one-click demo. Create an account to verify saved profile persistence.

## How recommendations work

Each topic is assigned a priority score using:

`priority = (100 - topic_score) * 0.8 + (importance * 4)`

Lower topic scores and higher importance raise priority. Before a first quiz, topics are labelled “Baseline needed”; they are not presented as measured student weaknesses. Time allocation is proportional to the priority score and constrained by the selected study duration.

## Main files

- `app.py` — Flask routes, authentication, question sets, scoring, study-plan algorithm and SQLite persistence.
- `templates/index.html` — login, dashboard, quiz, result, history and learning-path modal.
- `static/style.css` — visual styling, responsive layout, motion and reduced-motion fallback.
- `static/app.js` — frontend interaction and API integration.
- `studypilot.db` — created locally at first run; contains user profiles and attempts.

## APIs

- `GET /api/me`
- `POST /api/register`
- `POST /api/login`
- `POST /api/demo-login`
- `POST /api/logout`
- `GET /api/subjects?grade=Class%208`
- `POST /api/profile`
- `GET /api/dashboard`
- `GET /api/questions?mode=diagnostic&subject=Science`
- `POST /api/submit`
- `GET /api/plan?minutes=30&subject=Science`
- `GET /api/history`
- `GET /health`

## Prototype limitations

The question sets are curated demonstration content organised into curriculum bands. They are not a complete syllabus or a validated assessment for every school board. The recommendation logic is rule-based rather than a trained machine-learning model. Test with educators and students before making learning-outcome claims.

## Before public deployment

- Set `SECRET_KEY` to a unique secret value in the hosting environment.
- Configure a persistent disk or managed database. Ephemeral filesystem instances can lose SQLite data after restart/redeploy.
- Use HTTPS and avoid entering real sensitive student information in this hackathon prototype.
- Review current hosting policies and add appropriate privacy, CSRF, rate-limiting, and account recovery protections before production use.
