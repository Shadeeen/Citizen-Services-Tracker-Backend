# 🏛️ Citizen Services Tracker (CST)


---

##  Team
- **Shaden Hamda**
- **Mohammad Jadallah**

---

##  Overview

**Citizen Services Tracker (CST)** is a backend-focused Management Information System (MIS) built to help municipalities efficiently manage citizen-reported service issues.

The system enforces **structured workflows**, **SLA policies**, and **performance tracking**, while providing **geo-based visualization** and **analytics dashboards** to support data-driven decision making.

---

##  Project Goals

- Enable citizens to report municipal issues with location and evidence  
- Enforce a clear request lifecycle with strict workflow rules  
- Apply SLA policies with automated escalation  
- Assign requests based on zones, skills, and workload  
- Track performance, accountability, and citizen satisfaction  
- Provide real-time maps and analytical dashboards  

---

##  System Architecture

**CST is not a simple ticketing system.**  
It is built around:

- Workflow State Machine  
- SLA Enforcement & Escalation  
- Geo-Spatial Data Processing  
- Immutable Audit & Performance Logs  
- Analytics & Reporting Layer  

---

##  Tech Stack

###  Backend
- **FastAPI (Python)**
- **MongoDB (PyMongo)**
- RESTful APIs
- OpenAPI / Swagger documentation

###  Maps & Visualization
- OpenStreetMap
- Leaflet
- GeoJSON feeds (heatmaps & clustering)

###  Frontend
- Web dashboard (React-based views)

---

##  Core Features

###  Service Request Management
- Workflow lifecycle:  
  `new → triaged → assigned → in_progress → resolved → closed`
- Duplicate detection and request merging  
- Evidence uploads and internal notes  
- Geo-location stored using GeoJSON  

---

###  Citizen Portal
- Verified and anonymous reporting  
- Request tracking and status timeline  
- Comments and additional evidence  
- Service rating after resolution  

---

###  Service Agents & Assignment
- Agent and team management  
- Zone coverage and skill matching  
- Automatic assignment policies  
- Milestone tracking (arrival, work started, resolved)  

---

###  SLA & Performance Tracking
- Category- and priority-based SLA policies  
- Automated escalation rules  
- Immutable performance logs  
- SLA breach detection  

---

###  Analytics & Geo Visualization
- Live heat-map of open requests  
- Zone-based clustering  
- SLA compliance metrics  
- Exportable reports (CSV / PDF)  

---

##  What We Worked On

- Backend system design and architecture  
- REST API design and validation  
- Workflow and state machine enforcement  
- Concurrency handling and data consistency  
- MongoDB schema design and indexing  
- Geo-spatial data processing  
- Analytics and KPI computation  
- Git-based collaborative development  

---

##  Setup & Run

### Prerequisites
- Python 3.10+
- MongoDB
- Virtual Environment (recommended)

### Run Backend
```bash
git clone https://github.com/your-repo/cst-backend.git
cd cst-backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
