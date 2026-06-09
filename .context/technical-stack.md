# Technical Stack - WhoseOnFirst
**Version:** 1.0  
**Last Updated:** November 4, 2025  
**Status:** Approved

---

## Technology Stack Overview

### Core Technologies

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Backend Framework** | FastAPI | 0.115.0+ | REST API and web application framework |
| **ASGI Server** | Uvicorn | 0.30.1+ | High-performance async server |
| **Task Scheduler** | APScheduler | 3.10.4+ | Cron-based job scheduling |
| **Database (Phase 1)** | SQLite | 3.x | Embedded relational database |
| **Database (Phase 2+)** | PostgreSQL | 15+ | Enterprise-grade RDBMS |
| **ORM** | SQLAlchemy | 2.0.31+ | Database abstraction layer |
| **SMS Gateway** | Twilio Python SDK | 9.2.3+ | SMS delivery service |
| **Validation** | Pydantic | 2.8.2+ | Data validation and serialization |
| **Config Management** | python-dotenv | 1.0.1+ | Environment variable management |

---

## Backend Stack

### 1. FastAPI Framework

#### Why FastAPI?
- **Modern Python:** Built for Python 3.7+ with native async/await support
- **Type Safety:** Leverages Python type hints for automatic validation
- **Auto Documentation:** Generates OpenAPI (Swagger) and ReDoc automatically
- **Performance:** ASGI-based, significantly faster than traditional WSGI frameworks
- **Developer Experience:** Excellent IDE support, auto-completion, fewer bugs
- **Future-Proof:** Growing ecosystem, designed for modern microservices

#### Key Features We'll Use
- **Automatic API Documentation:** Critical for Phase 3 integrations (Teams, Slack)
- **Dependency Injection:** Clean architecture for database sessions, authentication
- **Background Tasks:** For non-blocking SMS sends
- **Request Validation:** Automatic validation using Pydantic models
- **Exception Handlers:** Centralized error handling
- **Middleware:** Logging, CORS, security headers

#### Example Structure
```python
from fastapi import FastAPI, Depends, HTTPException
from typing import List

app = FastAPI(
    title="WhoseOnFirst API",
    description="On-Call Rotation and SMS Notification System",
    version="1.0.0"
)

@app.get("/api/schedule/current", response_model=List[ScheduleEntry])
async def get_current_schedule(
    db: Session = Depends(get_db)
):
    """Get the current week's on-call schedule"""
    return schedule_service.get_current_week(db)
```

---

### 2. Uvicorn ASGI Server

#### Purpose
Production-grade ASGI server for serving FastAPI application

#### Configuration
```bash
# Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

#### Settings for Production
- **Workers:** 2 (RHEL 10 VM, limited resources)
- **Timeout:** 60 seconds
- **Keep-alive:** 5 seconds
- **Access Log:** Enabled for audit trail

---

### 3. APScheduler - Task Scheduling

#### Scheduler Configuration
```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///jobs.db')
}

scheduler = BackgroundScheduler(
    jobstores=jobstores,
    timezone=timezone('America/Chicago')
)

# Schedule daily SMS notifications at 8:00 AM CST
scheduler.add_job(
    func=send_daily_notifications,
    trigger=CronTrigger(hour=8, minute=0),
    id='daily_oncall_sms',
    name='Daily On-Call SMS Notification',
    replace_existing=True
)
```

#### Why APScheduler?
- **In-Process:** No external service required (unlike Celery)
- **Persistent Jobs:** Survives application restarts via SQLite job store
- **Timezone Support:** Native CST support, handles DST automatically
- **Job Monitoring:** Event listeners for tracking execution
- **Flexible Triggers:** Cron, interval, and one-time date triggers

#### Job Store Strategy
- **Development:** In-memory job store for testing
- **Production:** SQLite job store for persistence

---

## Database Stack

### Phase 1: SQLite

#### Why Start with SQLite?
- **Zero Configuration:** No separate database server to manage
- **Embedded:** Runs in-process with Python application
- **File-Based:** Single `.db` file, easy backups
- **Sufficient for Phase 1:** Handles 5-10 users, low-concurrency workload
- **ACID Compliant:** Full transaction support despite simplicity

#### SQLite Configuration
```python
# Database URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./whoseonfirst.db"

# Engine configuration
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for FastAPI
    pool_pre_ping=True,  # Verify connections before use
    echo=False  # Set to True for SQL debugging
)
```

#### SQLite Limitations to Monitor
- **Write Concurrency:** Locks entire database during writes
- **Max Connections:** ~100 concurrent connections (not an issue for us)
- **File Locking:** Could be problematic on network file systems
- **No User Management:** Security relies on file system permissions

#### When to Migrate to PostgreSQL
Triggers for migration:
- More than 10 active team members
- Multiple concurrent admin users
- High-frequency schedule updates (>100/hour)
- Need for row-level security
- Multi-team support (Phase 4)

---

### Phase 2+: PostgreSQL

#### Migration Strategy
Thanks to SQLAlchemy abstraction, migration requires minimal code changes:

```python
# Change database URL
SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/whoseonfirst"

# All SQLAlchemy models work unchanged
engine = create_engine(SQLALCHEMY_DATABASE_URL)
```

#### PostgreSQL Advantages
- **Concurrency:** MVCC allows multiple simultaneous writers
- **Advanced Features:** JSON columns, full-text search, window functions
- **Security:** Built-in authentication, row-level security (RLS)
- **Scalability:** Horizontal scaling via replication, sharding
- **Extensions:** PostGIS (if location features needed), pg_cron

---

### SQLAlchemy ORM

#### Why SQLAlchemy?
- **Database Agnostic:** Switch from SQLite to PostgreSQL with one line change
- **Async Support:** Compatible with FastAPI's async architecture
- **Migration Tools:** Alembic for database schema migrations
- **Type Safety:** Integrates with Pydantic for end-to-end type checking

#### Model Example
```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TeamMember(Base):
    __tablename__ = "team_members"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## SMS Integration

### Twilio Python SDK

#### Setup and Configuration
```python
from twilio.rest import Client
import os

# Load credentials from environment variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Initialize Twilio client (singleton pattern)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
```

#### SMS Sending Function
```python
def send_sms(to_number: str, message_body: str) -> dict:
    """Send SMS via Twilio with error handling and logging"""
    try:
        message = twilio_client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=to_number
        )
        
        return {
            "success": True,
            "sid": message.sid,
            "status": message.status,
            "error": None
        }
    except TwilioRestException as e:
        logger.error(f"Twilio error: {e.code} - {e.msg}")
        return {
            "success": False,
            "sid": None,
            "status": "failed",
            "error": str(e)
        }
```

#### Retry Logic with Exponential Backoff
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def send_sms_with_retry(to_number: str, message: str):
    """Send SMS with automatic retry on failure"""
    return send_sms(to_number, message)
```

#### Message Templates
```python
def format_shift_notification(member_name: str, duration_hours: int) -> str:
    """Format on-call notification message"""
    end_time = datetime.now() + timedelta(hours=duration_hours)
    
    return (
        f"WhoseOnFirst: Your on-call shift has started.\n"
        f"Duration: {duration_hours} hours (until {end_time.strftime('%I:%M %p %m/%d')})\n"
        f"Questions? Contact admin."
    )
```

---

## Frontend Stack

### Minimal Frontend Approach

#### Technologies
- **HTML5:** Semantic markup
- **CSS3:** Modern styling (CSS Grid, Flexbox)
- **Vanilla JavaScript:** No framework overhead
- **Fetch API:** For AJAX requests to FastAPI backend

#### Why Vanilla JS?
- **Simplicity:** No build process, no npm dependencies
- **Performance:** No framework overhead
- **Maintainability:** Straightforward code, easy for anyone to modify
- **Future Migration:** Can easily migrate to React/Vue if needed

#### Potential Enhancements (Future)
- **Tailwind CSS:** Utility-first CSS framework
- **Alpine.js:** Lightweight reactive framework (15KB)
- **HTMX:** Hypermedia-driven interactions without JavaScript

#### Example Structure
```javascript
// Fetch current schedule from API
async function loadSchedule() {
    try {
        const response = await fetch('/api/schedule/current');
        const schedule = await response.json();
        renderSchedule(schedule);
    } catch (error) {
        console.error('Failed to load schedule:', error);
        showError('Could not load schedule');
    }
}

// Render schedule in table
function renderSchedule(schedule) {
    const tbody = document.getElementById('schedule-body');
    tbody.innerHTML = schedule.map(entry => `
        <tr>
            <td>${entry.day}</td>
            <td>${entry.shift_number}</td>
            <td>${entry.team_member_name}</td>
            <td>${entry.duration_hours}h</td>
        </tr>
    `).join('');
}
```

---

## Development Tools

### Version Control
- **Git:** Distributed version control
- **GitHub:** Remote repository hosting
- **Branching Strategy:** 
  - `main` - Production-ready code
  - `develop` - Integration branch
  - `feature/*` - Feature branches
  - `hotfix/*` - Emergency fixes

### Development Environment

#### Primary IDE: Claude-Code CLI
- AI-assisted coding
- Context-aware code generation
- Automated testing support
- Documentation generation

#### Secondary Tools
- **VS Code:** For manual code review, debugging
- **Postman/Thunder Client:** API testing
- **SQLite Browser:** Database inspection

### Python Environment Management

#### Virtual Environment Setup
```bash
# Create virtual environment
python3 -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Requirements Management
```
# requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.30.1
sqlalchemy==2.0.31
apscheduler==3.10.4
twilio==9.2.3
python-dotenv==1.0.1
pydantic==2.8.2
pytz==2024.1

# Development dependencies
pytest==7.4.3
pytest-asyncio==0.21.1
httpx==0.25.2  # For testing FastAPI
black==23.12.0  # Code formatting
flake8==6.1.0   # Linting
mypy==1.7.1     # Type checking
```

---

## Deployment Stack

### Containerization: Docker

#### Dockerfile Strategy
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Docker Compose (Development)
```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - ./data:/app/data  # Persist SQLite database
    environment:
      - DATABASE_URL=sqlite:///./data/whoseonfirst.db
      - TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID}
      - TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN}
      - TWILIO_PHONE_NUMBER=${TWILIO_PHONE_NUMBER}
    restart: unless-stopped
```

### Target Platform: RHEL 10

#### System Requirements
- **OS:** Red Hat Enterprise Linux 10
- **Python:** 3.11+ (install via dnf)
- **Docker:** Podman (RHEL's Docker alternative) or Docker CE
- **Memory:** 2GB minimum, 4GB recommended
- **Disk:** 10GB for OS + app + logs
- **Network:** Access to Twilio API (outbound HTTPS)

#### Installation on RHEL 10
```bash
# Install Python 3.11
sudo dnf install python3.11 python3.11-pip

# Install Docker/Podman
sudo dnf install podman podman-compose

# Clone repository
git clone https://github.com/[org]/WhoseOnFirst.git
cd WhoseOnFirst

# Build container
podman build -t whoseonfirst:latest .

# Run container
podman run -d \
  --name whoseonfirst \
  -p 8000:8000 \
  -v ./data:/app/data \
  --env-file .env \
  whoseonfirst:latest
```

---

## Security Considerations

### Credential Management
- **Environment Variables:** All secrets in `.env` file (never committed)
- **Podman Secrets:** For production deployment on RHEL
- **File Permissions:** Restrict `.env` to owner read-only (600)

### Application Security
- **Input Validation:** Pydantic validates all API inputs
- **SQL Injection:** SQLAlchemy ORM prevents injection attacks
- **HTTPS:** Enforce TLS in production (nginx reverse proxy)
- **CORS:** Restrict origins in FastAPI middleware
- **Rate Limiting:** Implement to prevent abuse

### Data Security
- **Database Encryption:** File-level encryption for SQLite
- **Phone Number Handling:** Hash or encrypt in logs
- **Audit Trail:** Log all schedule changes, SMS sends
- **Backup Strategy:** Daily encrypted backups of database

---

## Monitoring and Logging

### Logging Strategy

#### Structured Logging
```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName
        }
        return json.dumps(log_obj)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler('/var/log/whoseonfirst/app.log'),
        logging.StreamHandler()
    ]
)
```

#### Log Categories
- **Application Logs:** General app events, errors
- **SMS Logs:** All SMS attempts, success/failure, Twilio SIDs
- **Scheduler Logs:** Job execution, missed jobs, errors
- **API Logs:** HTTP requests, response times, errors
- **Audit Logs:** Schedule changes, team member updates

### Health Checks

#### FastAPI Health Endpoint
```python
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": check_database_connection(),
        "scheduler": scheduler.running,
        "twilio": check_twilio_connection()
    }
```

### Future Monitoring Tools
- **Prometheus:** Metrics collection
- **Grafana:** Visualization dashboards
- **Sentry:** Error tracking and alerting

---

## Testing Strategy

### Testing Levels

#### 1. Unit Tests (pytest)
```python
import pytest
from datetime import datetime

def test_rotation_algorithm():
    """Test that circular rotation algorithm works correctly"""
    team = create_test_team(7)
    schedule = generate_schedule(team, weeks=4)

    # Assert all shifts covered each week
    assert len(schedule) == 6 * 4  # 6 shifts * 4 weeks

    # Assert members rotate correctly (person moves forward one position each week)
    week_1_shift_1 = [s for s in schedule if s.week == 1 and s.shift_number == 1][0]
    week_2_shift_2 = [s for s in schedule if s.week == 2 and s.shift_number == 2][0]
    assert week_1_shift_1.person == week_2_shift_2.person  # Same person moved to next shift
```

#### 2. Integration Tests
```python
@pytest.mark.asyncio
async def test_send_notification_flow():
    """Test complete notification flow"""
    # Create test schedule entry
    schedule_entry = create_test_schedule_entry()
    
    # Trigger notification
    result = await send_notification(schedule_entry)
    
    # Assert SMS was sent
    assert result.success is True
    assert result.sid is not None
    
    # Assert database was updated
    log_entry = get_notification_log(schedule_entry.id)
    assert log_entry.status == "sent"
```

#### 3. API Tests (httpx + FastAPI TestClient)
```python
from fastapi.testclient import TestClient

client = TestClient(app)

def test_get_current_schedule():
    """Test GET /api/schedule/current endpoint"""
    response = client.get("/api/schedule/current")
    assert response.status_code == 200
    assert "schedule" in response.json()
```

### Test Coverage Goal
- **Target:** 80%+ code coverage
- **Critical Paths:** 100% coverage (scheduler, SMS sending, rotation algorithm)

---

## Performance Targets

### Response Time Goals
- **API Endpoints:** <500ms (95th percentile)
- **Database Queries:** <100ms (95th percentile)
- **SMS Delivery Trigger:** <60 seconds from scheduled time
- **Page Load:** <2 seconds (full page)

### Scalability Targets
- **Team Members:** Support up to 20 (Phase 1), 100+ (Phase 2+)
- **Concurrent Users:** 5-10 (Phase 1), 50+ (Phase 2+)
- **Database Size:** <100MB (Phase 1), <10GB (Phase 2+)
- **SMS Volume:** 10/day (Phase 1), 1000/day (Phase 2+)

---

## Technology Decision Matrix

| Decision Factor | SQLite | PostgreSQL | Winner (Phase 1) |
|----------------|--------|------------|------------------|
| Setup Complexity | ⭐⭐⭐⭐⭐ | ⭐⭐ | SQLite |
| Concurrency | ⭐⭐ | ⭐⭐⭐⭐⭐ | SQLite (low concurrency) |
| Features | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | SQLite (features not needed yet) |
| Scalability | ⭐⭐ | ⭐⭐⭐⭐⭐ | SQLite (small scale) |
| Maintenance | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | SQLite |

| Decision Factor | Flask | FastAPI | Winner |
|----------------|-------|---------|--------|
| Performance | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | FastAPI |
| Documentation | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | FastAPI |
| Type Safety | ⭐⭐ | ⭐⭐⭐⭐⭐ | FastAPI |
| Learning Curve | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | FastAPI |
| Ecosystem | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | FastAPI |
| Async Support | ⭐⭐ | ⭐⭐⭐⭐⭐ | FastAPI |

---

## Dependency Versions and Compatibility

### Python Version Requirements
- **Minimum:** Python 3.11
- **Recommended:** Python 3.11.7+
- **Maximum:** Python 3.12.x (test for compatibility)

### Critical Dependencies
All versions are pinned for reproducibility:

```txt
# Core Framework
fastapi==0.115.0
uvicorn[standard]==0.30.1

# Database
sqlalchemy==2.0.31
alembic==1.13.1  # For migrations

# Scheduling
apscheduler==3.10.4
pytz==2024.1

# SMS
twilio==9.2.3

# Validation
pydantic==2.8.2
pydantic-settings==2.2.1

# Utilities
python-dotenv==1.0.1
httpx==0.25.2
```

### Version Update Policy
- **Security patches:** Apply immediately
- **Minor versions:** Update quarterly
- **Major versions:** Evaluate carefully, test thoroughly

---

## Migration Paths

### SQLite → PostgreSQL Migration

#### Step 1: Prepare Code
All SQLAlchemy code is already database-agnostic

#### Step 2: Export Data
```bash
# Export SQLite to SQL dump
sqlite3 whoseonfirst.db .dump > backup.sql
```

#### Step 3: Convert and Import
```bash
# Install conversion tool
pip install sqlite3-to-postgres

# Convert SQLite DB to PostgreSQL
sqlite3-to-postgres -f whoseonfirst.db -d whoseonfirst -u postgres
```

#### Step 4: Update Configuration
```python
# Change in .env file
DATABASE_URL=postgresql://user:pass@localhost/whoseonfirst
```

#### Step 5: Test Thoroughly
Run full test suite to verify migration

---

## Cost Considerations

### Twilio Pricing (Approximate)
- **SMS Outbound (US):** $0.0079 per message
- **Phone Number:** $1.50/month
- **Monthly Estimate:** ~$3-5 for 7-person team (7 SMS/day × 30 days × $0.0079)

### Infrastructure Costs
- **RHEL 10 VM:** Internal hosting (no additional cost)
- **Development:** Free (local Mac + Proxmox)
- **Docker/Podman:** Free and open source

### Total Monthly Operating Cost
- **Phase 1:** <$10/month (Twilio only)
- **Phase 2:** <$20/month (if adding PostgreSQL on separate VM)

---

## Appendix: Useful Commands

### Development Workflow
```bash
# Start development server
uvicorn main:app --reload

# Run tests
pytest tests/ -v --cov

# Format code
black .

# Type check
mypy .

# Lint code
flake8 .

# Database migration
alembic upgrade head
```

### Docker Commands
```bash
# Build image
docker build -t whoseonfirst:latest .

# Run container
docker run -d -p 8000:8000 --name whoseonfirst whoseonfirst:latest

# View logs
docker logs -f whoseonfirst

# Stop container
docker stop whoseonfirst

# Remove container
docker rm whoseonfirst
```

### Production Deployment (RHEL 10)
```bash
# Pull latest code
git pull origin main

# Rebuild container
podman build -t whoseonfirst:latest .

# Stop old container
podman stop whoseonfirst

# Remove old container
podman rm whoseonfirst

# Start new container
podman run -d \
  --name whoseonfirst \
  -p 8000:8000 \
  -v ./data:/app/data \
  --env-file .env \
  --restart=always \
  whoseonfirst:latest
```

---

*Document Version: 1.0*  
*Last Updated: November 4, 2025*  
*Next Review: Start of Development Phase*
