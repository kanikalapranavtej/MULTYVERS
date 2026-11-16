# MULTYVERS — Campus Event Management Platform

MULTYVERS is a centralized, role-based web application for managing campus events. It brings students, event organizers and administrators together in one platform, covering the event lifecycle from organizer requests and event proposals to student registration, venue scheduling, attendance tracking and event analytics.

---

## Contents

- [1. Problem and objective](#1-problem-and-objective)
- [2. Main users and portals](#2-main-users-and-portals)
- [3. Features](#3-features)
- [4. Technology stack](#4-technology-stack)
- [5. Application architecture](#5-application-architecture)
- [6. Database design](#6-database-design)
- [7. Security and validation](#7-security-and-validation)
- [8. Project structure](#8-project-structure)
- [9. Setup and installation](#9-setup-and-installation)
- [10. Initialize the database](#10-initialize-the-database)
- [11. Run the application](#11-run-the-application)
- [12. Run the tests](#12-run-the-tests)
- [13. Bash helper scripts](#13-bash-helper-scripts)
- [14. Configuration](#14-configuration)
- [15. Git and collaborative development](#15-git-and-collaborative-development)

---

## 1. Problem and objective

Campus activities such as technical events, workshops, competitions, seminars and cultural programmes require several tasks to be coordinated:

- Publishing event information.
- Receiving and managing registrations.
- Maintaining participant details.
- Checking event capacity and registration deadlines.
- Allocating venues and time slots.
- Reviewing and approving event proposals.
- Recording attendance.
- Managing organizer accounts.
- Reviewing event activity and performance.

When these activities are handled through separate manual processes, information can become scattered and coordination becomes difficult.

**The objective of MULTYVERS** is to centralize these activities in one web application. The system uses role-based access so that students, organizers and administrators see the functions relevant to their responsibilities.

MULTYVERS is intended to be more than an event-listing website: it supports event submission and approval, registration management, venue checks, participant records, QR-based attendance, administrative controls and analytics.

---

## 2. Main users and portals

### Student Portal

The Student Portal is for students who want to discover campus events and manage their participation.

### Organizer Portal

The Organizer Portal is for approved organizers who create events and manage participants, attendance and event information.

### Admin Portal

The Admin Portal provides platform-level supervision. Administrators manage users, organizer requests, event approvals, venues and categories.

The three portals are part of the same Flask application and use the same underlying database.

---

## 3. Features

### 3.1 Student Portal

- **Account registration and login:** Students can create accounts and sign in.
- **Student dashboard:** Displays student-related information and provides navigation to event and registration pages.
- **Event discovery:** Browse approved events and view event details, including descriptions, dates, venues and capacity information.
- **Search and filtering:** Find events using the available event search and date-related filters.
- **Event registration:** Register for eligible events.
- **Registration validation:** The backend checks conditions such as duplicate registration, event approval, capacity and registration deadline.
- **Registration management:** View registration information and cancel registrations where permitted.
- **QR ticket access:** Students can access QR-related ticket functionality associated with their registrations.

### 3.2 Organizer Portal

- **Organizer account request:** A prospective organizer can submit an account request.
- **Approval workflow:** Organizer requests are subject to administrator approval. Pending or inactive accounts are restricted from protected organizer functions.
- **Organizer dashboard:** Provides an overview of the organizer's events, their statuses, capacity and registration information.
- **Event creation:** Submit an event with a title, description, category, venue, capacity, start and end times, and registration deadline.
- **Event editing and cancellation:** Manage events belonging to the signed-in organizer, subject to the application's workflow and permissions.
- **Event review status:** Organizers can see the status of submitted events.
- **Venue availability checking:** Check whether a venue has a conflicting event during a proposed time interval.
- **Participant management:** View participants registered for the organizer's events, including relevant registration and attendance information.
- **Participant search and filtering:** Find participant records and filter them by the available registration status.
- **Pagination:** Browse participant records in pages.
- **Participant CSV export:** Export participant information for further use.
- **QR-based attendance:** The attendance workflow uses QR functionality and backend validation to record check-ins.
- **Attendance records:** Organizers can view attendance information associated with their events.
- **Analytics dashboard:** View event and registration statistics, attendance information, attendance rates and event-performance summaries.
- **Analytics CSV export:** Export supported analytics data.

### 3.3 Admin Portal

- **Admin dashboard:** Provides a summary of platform activity, including student and organizer counts, organizer requests, event counts, pending events and registration information.
- **Student management:** View and search student accounts, inspect related registration information, and activate or deactivate accounts.
- **Organizer management:** View, create, edit, approve, reject, activate, deactivate and delete organizer accounts where permitted.
- **Organizer request review:** Review pending organizer requests and approve or reject them.
- **Event approval:** Review submitted events and approve or reject pending proposals.
- **Venue management:** Create, view, edit and delete venues where database relationships permit. Venue records include location and capacity information.
- **Category management:** Create, view, edit, search and delete event categories where permitted.
- **Administrative oversight:** Manage the core records that support event operations across the platform.

### 3.4 Venue conflict checking

Venue availability checking helps prevent overlapping bookings at the same venue. The proposed venue, start time and end time are checked against existing event bookings. A conflicting time interval should not be accepted.

### 3.5 QR attendance

The attendance functionality connects an event registration with an attendance record. The backend validates the attendance operation and the database schema includes uniqueness constraints intended to prevent duplicate attendance records for the same registration and event/user combination.

The exact QR ticket and check-in flow should be followed in the application itself; this README does not assume that a QR ticket and an organizer attendance-scanner QR are the same token or workflow.

### 3.6 CSV exports

CSV export functionality is available in the participant-management and analytics areas. It allows supported records or summaries to be downloaded for use outside the application.

---

## 4. Technology stack

| Area | Technologies | Purpose |
|---|---|---|
| Backend | Python, Flask | Server-side application and request handling |
| Application structure | Flask Blueprints | Organizes route functionality into modules |
| Authentication | Flask-Login | Login sessions and user authentication |
| Forms and CSRF | Flask-WTF, WTForms | Form support and CSRF protection |
| Security utilities | Werkzeug | Password hashing and related utilities |
| Frontend | HTML, CSS, JavaScript | Page structure, styling and browser-side behaviour |
| Templates | Jinja2 | Dynamic HTML rendering |
| Database | SQLite, SQL | Relational data storage and queries |
| QR and image support | qrcode, Pillow | QR/image-related functionality |
| Testing | pytest | Automated functional tests |
| Development tools | VS Code, Git, GitHub, Git Bash | Development, version control and command-line workflow |
| Environment | Python virtual environment | Isolates project dependencies |

The exact pinned Python package versions are listed in `requirements.txt`.

---

## 5. Application architecture

MULTYVERS uses a modular Flask application structure.

### 5.1 Application factory

The application is created through `create_app()` in `app/__init__.py`. The factory loads configuration, initializes extensions and database handling, and registers the application's route blueprints.

### 5.2 Flask Blueprints

The routes are separated by responsibility. The main route modules include:

| Module | Responsibility |
|---|---|
| `auth.py` | Student registration, login, logout and organizer account requests |
| `main.py` | Main application and landing-page routes |
| `events.py` | Event operations |
| `registrations.py` | Student event registrations |
| `organizer_management.py` | Organizer account-management operations |
| `admin_students.py` | Administrator student-management operations |
| `venues.py` | Venue-related operations |
| `participants.py` | Participant-management operations |
| `attendance.py` | Attendance operations |
| `analytics.py` | Analytics data operations |
| `portal_pages.py` | Role-specific portal pages |
| `pages.py` | General feature pages |
| `venue_pages.py` | Venue-management pages |
| `category_pages.py` | Category-management pages |
| `attendance_pages.py` | Attendance pages |
| `analytics_pages.py` | Analytics pages |

### 5.3 Frontend organization

- `app/templates/` contains Jinja2 HTML templates.
- `app/templates/components/` contains reusable interface components.
- `app/static/css/` contains stylesheets.
- `app/static/js/` contains browser-side JavaScript.

### 5.4 Request flow

At a high level, a browser request is handled as follows:

1. The browser requests a page or performs an application action.
2. Flask routes the request to the relevant registered Blueprint.
3. Authentication and role checks protect restricted operations.
4. The route uses database operations where data must be read or changed.
5. The application returns a rendered Jinja2 page or an appropriate response.
6. The browser displays the result.

**Simplified architecture:**

```text
                 STUDENT PORTAL
                       |
                 ORGANIZER PORTAL
                       |
                   ADMIN PORTAL
                       |
                 HTML / CSS / JS
                       |
                 FLASK APPLICATION
                 (create_app)
                       |
              REGISTERED BLUEPRINTS
                       |
          Authentication / Role Checks
                       |
                 DATABASE LAYER
                       |
                  SQLITE DB
```

---

## 6. Database design

MULTYVERS uses SQLite as its relational database. The schema is defined in `database/schema.sql`.

The schema contains six main tables:

| Table | Purpose | Important relationships |
|---|---|---|
| `users` | Stores student, organizer and administrator accounts | Referenced by events, registrations and attendance |
| `categories` | Stores event categories | Referenced by events |
| `venues` | Stores venue name, location and capacity | Referenced by events |
| `events` | Stores event details, schedule, capacity and status | References organizer, category and venue |
| `registrations` | Stores student registrations for events | References users and events |
| `attendance` | Stores attendance/check-in records | References registrations, events and users |

### 6.1 Important database rules

The schema uses:

- Primary keys to identify records.
- Foreign keys to maintain relationships between tables.
- Unique constraints to prevent duplicate values or duplicate relationships.
- `CHECK` constraints to restrict certain values, such as roles, statuses and positive capacities.
- Indexes on frequently queried event, registration and attendance fields.
- A uniqueness rule on the user/event registration pair.
- Attendance uniqueness rules to help prevent duplicate attendance records.

Foreign-key enforcement is enabled for database connections used by the application.

### 6.2 Main relationships

- One organizer can create multiple events.
- Each event references a category and a venue.
- Students and events are connected through registrations.
- Attendance records refer to the relevant registration, event and user.
- The database constraints help preserve the validity of these relationships.

For the authoritative field definitions and constraints, refer to `database/schema.sql`.

---

## 7. Security and validation

The implementation includes the following security and validation mechanisms:

- Passwords are stored as hashes using Werkzeug rather than as plain-text passwords.
- Flask-Login manages authenticated user sessions.
- Role-based route protection is implemented through application decorators.
- Protected routes check the user's role and active-account status.
- Organizer approval status is used to restrict access to organizer functionality.
- Flask-WTF CSRF protection is enabled in the application configuration.
- SQL statements use parameterized values in the application code.
- Database constraints provide an additional layer of data integrity.
- The registration and login implementation applies the `@multyvers.in` email-domain rule outside testing mode.
- The official administrator identity is reserved as `admin@multyvers.in` by the current application logic.

Do not use the development defaults for a public deployment. Configure a strong secret key and administrator password before using the application beyond local development.

---

## 8. Project structure

The main application files are organized as follows:

```text
MULTYVERS/
│
├── app/
│   ├── routes/
│   │   ├── auth.py
│   │   ├── main.py
│   │   ├── events.py
│   │   ├── registrations.py
│   │   ├── organizer_management.py
│   │   ├── admin_students.py
│   │   ├── venues.py
│   │   ├── participants.py
│   │   ├── attendance.py
│   │   ├── analytics.py
│   │   └── ...page route modules
│   │
│   ├── templates/
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   │
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── decorators.py
│   ├── extensions.py
│   └── models.py
│
├── database/
│   ├── schema.sql
│   └── init_db.py
│
├── scripts/
│   ├── setup.sh
│   ├── run.sh
│   └── test.sh
│
├── tests/
│   ├── conftest.py
│   └── test_*.py
│
├── report/
│   ├── main.tex
│   ├── references.bib
│   └── figures/
│
├── Beamer Presentation/
│   ├── main.tex
│   └── SLIDES.pdf
│
├── requirements.txt
├── run.py
├── .env.example
├── .gitignore
└── README.md
```

Some generated files, local databases and virtual-environment files may not be tracked by Git. The structure above shows the main source and documentation areas rather than every generated file.

---

## 9. Setup and installation

### 9.1 Prerequisites

Install the following:

- Python 3.10 or newer (Python 3.12 is suitable for the deployment configuration shown in the project history).
- Git.
- Git Bash on Windows, or a Bash-compatible terminal on Linux/macOS.

Check the installed versions:

```bash
python --version
git --version
```

### 9.2 Clone the repository

```bash
git clone https://github.com/kanikalapranavtej/MULTYVERS.git
cd MULTYVERS
```

### 9.3 Create a virtual environment

**Windows — Git Bash:**

```bash
python -m venv venv
source venv/Scripts/activate
```

**Linux/macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 9.4 Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The project also provides a setup helper script:

```bash
bash scripts/setup.sh
```

Run this from the project root. It creates `venv` if necessary, activates it for the script process and installs `requirements.txt`.

---

## 10. Initialize the database

The database schema is stored in `database/schema.sql`. For a fresh local setup, initialize the SQLite database with:

```bash
python database/init_db.py
```

This creates `database/multyvers.db` and applies the schema. The application uses this database path by default.

The application initialization code also applies its organizer account-status migration and ensures the configured default administrator exists when the database has already been initialized.

**Important:** The SQLite database contains application data and is excluded from Git by `.gitignore`. A fresh clone should initialize its own local database. Do not overwrite a database that contains data you need to keep.

---

## 11. Run the application

Make sure the virtual environment is activated and the database has been initialized.

Start the application:

```bash
python run.py
```

Or use the Bash helper:

```bash
bash scripts/run.sh
```

The development server uses port `5000` by default. Open:

```text
http://127.0.0.1:5000
```

To use a different port, set the `PORT` environment variable before starting the application.

Stop the local server with `Ctrl+C`.

---

## 12. Run the tests

The project uses Pytest and Flask's test client.

With the virtual environment activated, run:

```bash
python -m pytest -q
```

For more detailed test names and results:

```bash
python -m pytest -v
```

Or use the Bash helper:

```bash
bash scripts/test.sh
```

### Test setup

The test configuration in `tests/conftest.py` creates a temporary SQLite database for tests, applies the schema and creates test users. This keeps test data isolated from the normal application database.

### Test coverage areas

The existing test suite is organized around these areas:

A. Application, authentication and authorization  
B. Student portal and registrations  
C. Event management  
D. Organizer portal and organizer management  
E. Participants and attendance  
F. Admin portal and student management  
G. Venues and categories  
H. Database and analytics  

A previously recorded run reported:

```text
222 passed in 84.25s
```

This is a recorded result from the project's development workflow, not a guarantee that every future environment or code revision will produce the same result. Run the test command above to verify the current checkout.

---

## 13. Bash helper scripts

The `scripts/` directory contains three Bash scripts:

| Script | Purpose |
|---|---|
| `scripts/setup.sh` | Creates the Python virtual environment if needed and installs dependencies |
| `scripts/run.sh` | Activates the virtual environment and starts `run.py` |
| `scripts/test.sh` | Activates the virtual environment and runs the Pytest suite |

Run them from the project root:

```bash
bash scripts/setup.sh
bash scripts/run.sh
bash scripts/test.sh
```

The scripts are intended to avoid repeatedly typing the longer setup, run and test commands.

---

## 14. Configuration

The repository contains `.env.example` as a reference for configuration values. The application reads the following environment variables directly from the process environment:

| Variable | Purpose | Development example |
|---|---|---|
| `MULTYVERS_SECRET_KEY` | Flask session/signing secret | Set a long random secret |
| `MULTYVERS_ADMIN_PASSWORD` | Password used for the configured administrator | Set a strong password |
| `COOKIE_SECURE` | Enables secure session cookies over HTTPS | `false` for local HTTP |
| `MULTYVERS_DEBUG` | Enables Flask debug mode in `run.py` | `false` |
| `PORT` | Local server port | `5000` |

The `.env.example` file is a template; the application code shown in this repository does not automatically load a `.env` file. Set the variables in your terminal or hosting provider's environment-variable settings.

**Git Bash example:**

```bash
export MULTYVERS_SECRET_KEY="replace-with-a-long-random-secret"
export MULTYVERS_ADMIN_PASSWORD="choose-a-strong-password"
export COOKIE_SECURE="false"
export MULTYVERS_DEBUG="false"
export PORT="5000"
```

Then start the application in the same terminal:

```bash
python run.py
```

The current development configuration has fallback values, including a default administrator password of `password` when `MULTYVERS_ADMIN_PASSWORD` is not set. Change this before using the application with real users. The configured administrator email is:

```text
admin@multyvers.in
```

Never commit real secrets or share them in public issue reports. Keep `.env` and other secret-bearing files out of Git.

---

## 15. Git and collaborative development

Git and GitHub were used to maintain the source code and coordinate feature development.

The repository includes feature branches associated with areas such as:

- Event discovery.
- Landing page.
- Venue management.
- Participant management.
- QR attendance.
- Analytics dashboard.

A feature-branch workflow allows work to be developed and reviewed separately before integration into the main branch.

Typical Git commands used during development include:

```bash
git status
git branch
git switch -c feature/feature-name
git add .
git commit -m "Describe the implemented change"
git push -u origin feature/feature-name
```

After a feature is ready, it can be merged into the main development branch using the team's agreed review and merge process.

Before committing, check that local databases, virtual environments, caches and secrets are not staged:

```bash
git status
```

The repository's `.gitignore` excludes common local files such as virtual environments, `.env`, SQLite database files, Python caches and pytest cache files.

---
---

## Repository

**GitHub:** https://github.com/kanikalapranavtej/MULTYVERS


