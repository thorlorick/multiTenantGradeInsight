# Grade Insight — Simple Grade Sharing for Schools

**Grade Insight** is a straightforward web application that helps teachers share student grades with parents in real-time. Teachers upload CSV files with grades and assignments, and parents can immediately view their student's progress through a simple web interface.

The multi-tenant architecture allows multiple schools to use the same application independently, with complete data isolation between schools.

---
✨ Features
- 🧑🏫 Flexible CSV Upload - Use Grade Insight template, Google Classroom exports or any .csv that follows our structure (see below)
- 🔍 Automatic Data Cleaning - Smart parsing and normalization of grade data
- 📈 Student/Parent Dashboard - Clean, simple progress visualization
- 🔄 Smart Updates - Intelligent duplicate detection and data merging
- 🐳 Docker Ready - Containerized FastAPI application for easy deployment
- ⚡ Fast Performance - Built on FastAPI for high-performance 
- 📱 Responsive Design - Works seamlessly on desktop and mobile devices

## What It Does

### 🧑‍🏫 For Teachers
- Upload CSV files with student grades and assignments
- Use tags to organize classes, subjects, or terms
- Each teacher’s data is isolated within their school
- No training or setup required—just upload and go

### 👪 For Parents
- See real-time updates on student progress
- View assignments, marks, and trends by teacher/class
- Filter by subject, term, or custom tags
- Access through a school-branded portal (e.g., `yourschool.gradeinsight.com`)

### 🏫 For Schools
- Host multiple schools in one deployment with full tenant isolation
- Lightweight, scalable, and easy to self-host
- Keeps school data completely siloed from others

---

## Getting Started

### Requirements
- [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
- `.env` file (see `.env.example`)
- Valid CSV file matching the expected format

### Quick Start

```bash
git clone https://github.com/your-org/multiTenantGradeInsight.git
cd multiTenantGradeInsight
cp .env.example .env  # edit with your own credentials and secrets
docker compose up --build
```

The app will be available at `http://len.uiscan.com`.

---

## Folder Structure

```
multiTenantGradeInsight/
├── app/                    # FastAPI application
│   ├── main.py             # Entry point
│   ├── config.py           # Environment/config settings
│   ├── database/           # DB connection, models, and schemas
│   ├── routers/            # API routes (CSV upload, authentication, etc.)
│   ├── services/           # Business logic
│   └── templates/          # HTML templates for frontend
├── Dockerfile              # Container image definition
├── docker-compose.yml      # Orchestration for API, DB, etc.
├── .env.example            # Sample environment config
├── requirements.txt        # Python dependencies
└── README.md
```

---

## Environment Variables

Make sure your `.env` includes:

```
POSTGRES_DB=gradeinsight
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
DATABASE_URL=postgresql+psycopg2://your_user:your_password@postgres:5432/gradeinsight

SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

You may need to adjust other variables depending on deployment setup.

---

## CSV Format

Grade Insight expects a standardized CSV format for uploads:

| Row | Description                                  |
|-----|----------------------------------------------|
| 1   | Assignment names (e.g., "Test 1", "Essay")    |
| 2   | Assignment dates (optional)                  |
| 3   | Max points per assignment                    |
| 4+  | Student data rows                            |

**Required student columns:**
- `student_email` (used as unique ID)
- `first_name`
- `last_name`

**Example:**

```
### CSV Format

last_name,first_name,email,Assignment 1,Assignment 2,Assignment 3
DATE,-,-,2025-06-01,2025-06-03,2025-06-05
POINTS,-,-,100,100,100
Smith,Alice,alice.smith@example.com,85,90,78
Johnson,Bob,bob.johnson@example.com,88,92,81
Brown,Charlie,charlie.brown@example.com,92,85,89

```

---

## Multi-Tenant Architecture

- Each school acts as a tenant and is fully isolated
- School-specific subdomains (e.g., `greenvalley.gradeinsight.com`)
- PostgreSQL can support logical separation via schemas or prefixing
- Tenant is determined via subdomain or API key

---

<!-- ## Deployment Notes

- Designed to run behind a reverse proxy (e.g., NGINX, Traefik)
- TLS certificates can be added with Let’s Encrypt or custom certs
- Email and authentication systems can be integrated later (roadmap)
-->
---

## Roadmap

- [ ] Google Classroom integration (no-CSV mode)
- [ ] Admin dashboard for school-wide reporting
- [ ] User authentication and role management

---

## License

This project is licensed under the MIT License.

