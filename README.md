# Grade Insight — Simple Grade Sharing for Schools

**Grade Insight** is a straightforward web application that helps teachers share student grades with parents in real-time. Teachers upload CSV files with grades and assignments, and parents can immediately view their student's progress through a simple web interface.

The multi-tenant architecture allows multiple schools to use the same application independently, with complete data isolation between schools.

---

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

The app will be available at `http://localhost`.

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
- `student_number` (used as unique ID)
- `first_name`
- `last_name`

**Example:**

```
student_number,first_name,last_name,Test 1,Essay
,date,date,2024-09-12,2024-09-20
,max,max,20,30
12345,Jane,Doe,18,27
67890,John,Smith,15,22
```

---

## Multi-Tenant Architecture

- Each school acts as a tenant and is fully isolated
- School-specific subdomains (e.g., `greenvalley.gradeinsight.com`)
- PostgreSQL can support logical separation via schemas or prefixing
- Tenant is determined via subdomain or API key

---

## Deployment Notes

- Designed to run behind a reverse proxy (e.g., NGINX, Traefik)
- TLS certificates can be added with Let’s Encrypt or custom certs
- Email and authentication systems can be integrated later (roadmap)

---

## Roadmap

- [ ] Google Classroom integration (no-CSV mode)
- [ ] Grade trends and analytics for parents
- [ ] Admin dashboard for school-wide reporting
- [ ] User authentication and role management

---

## License

This project is licensed under the MIT License.

