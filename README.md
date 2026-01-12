Citizen Services Tracker (CST)

FastAPI + MongoDB Backend

1) System concept (what the backend must enforce)

CST is not just CRUD tickets. It must enforce:

Strict workflow/state machine: new → triaged → assigned → in_progress → resolved → closed with rule-based transitions and mandatory fields per transition.

SLA policy selection + escalation rules per category/zone/priority with automated escalation steps.

Duplicate detection and merge into a master request.

Geo-enabled requests stored as GeoJSON with 2dsphere index, used for live heatmap/clustering and zone summaries.

Assignment policy based on zone + skills + workload + availability (on shift).

Immutable audit/performance logs (event stream) used to compute KPIs like resolution time, SLA state, escalation count, etc.

2) Core database collections (MongoDB)

The project explicitly uses these collections:

service_requests (main requests)

citizens (profiles and preferences)

service_agents (agents/teams)

performance_logs (audit/event stream + computed KPIs + ratings)

geo_feeds (GeoJSON map feeds/snapshots)

Below are recommended full field sets (aligned to the provided sample schemas and required features).

A) service_requests collection
Purpose

The single source of truth for each request (ticket), including: citizen reference, classification, workflow state, SLA policy, timestamps, geo-location, duplicates, assignment, evidence, and internal notes.

Document fields (schema)
{
  "_id": "ObjectId",

  "request_id": "string (human readable unique e.g., CST-2026-0001)",

  "citizen_ref": {
    "citizen_id": "ObjectId | null",
    "anonymous": "boolean",
    "contact_channel": "string enum: email|sms|none"
  },

  "category": "string (e.g., pothole, water_leak, missed_trash)",
  "sub_category": "string | null",
  "description": "string",

  "tags": ["string"],

  "status": "string enum: new|triaged|assigned|in_progress|resolved|closed",
  "priority": "string enum: P1|P2|P3|P4",

  "workflow": {
    "current_state": "same as status",
    "allowed_next": ["string"],
    "transition_rules_version": "string (e.g., v1.2)"
  },

  "sla_policy": {
    "policy_id": "string",
    "target_hours": "number",
    "breach_threshold_hours": "number",
    "escalation_steps": [
      { "after_hours": "number", "action": "string" }
    ]
  },

  "timestamps": {
    "created_at": "datetime",
    "triaged_at": "datetime | null",
    "assigned_at": "datetime | null",
    "in_progress_at": "datetime | null",
    "resolved_at": "datetime | null",
    "closed_at": "datetime | null",
    "updated_at": "datetime"
  },

  "location": {
    "type": "Point",
    "coordinates": ["number(lon)", "number(lat)"],
    "address_hint": "string | null",
    "zone_id": "string (e.g., ZONE-DT-01)"
  },

  "duplicates": {
    "is_master": "boolean",
    "master_request_id": "string | null (request_id of master)",
    "linked_duplicates": ["string (request_id)"]
  },

  "assignment": {
    "assigned_agent_id": "ObjectId | null",
    "auto_assign_candidate_agents": ["ObjectId"],
    "assignment_policy": "string (e.g., zone+skill+workload)"
  },

  "evidence": [
    {
      "type": "string enum: photo|video|file",
      "url": "string",
      "sha256": "string",
      "uploaded_by": "string enum: citizen|agent|staff",
      "uploaded_at": "datetime"
    }
  ],

  "internal": {
    "notes": ["string"],
    "visibility": "string enum: internal_only"
  }
}

Required indexes

request_id unique index

location 2dsphere index (GeoJSON Point)

Common query indexes:

status, priority, category, location.zone_id, timestamps.created_at, timestamps.updated_at

Duplicate lookup: duplicates.master_request_id, duplicates.is_master

Key logic rules for service_requests
1) Create request (idempotent)

API: POST /requests/ must support idempotency key (same key = return same created request, no duplicates created).

On create:

set status = new

set timestamps: created_at, updated_at

compute zone_id from coordinates

select priority

select sla_policy based on (category + zone + priority)

emit performance log event: created

2) Duplicate detection + merge

Detect duplicates using:

same category

distance radius

time window

Master logic:

one master request

others reference it via master_request_id

3) Workflow/state machine transitions

API: PATCH /requests/{request_id}/transition validates:

allowed transitions

required fields

timestamps

writes event logs

Allowed transitions:

new → triaged

triaged → assigned

assigned → in_progress

in_progress → resolved

resolved → closed

4) Manual escalation

API: POST /requests/{request_id}/escalate

B) citizens collection
Purpose

Stores citizen profile, verification, contact info, preferences, and stats.

{
  "_id": "ObjectId",
  "full_name": "string | null",
  "verification": {
    "state": "string enum: unverified|verified",
    "method": "string",
    "verified_at": "datetime | null"
  },
  "contacts": {
    "email": "string | null",
    "phone": "string | null"
  },
  "preferences": {
    "preferred_contact": "string",
    "language": "string",
    "privacy": {
      "default_anonymous": "boolean",
      "share_publicly_on_map": "boolean"
    },
    "notifications": {
      "on_status_change": "boolean",
      "on_resolution": "boolean"
    }
  },
  "address": {
    "neighborhood": "string | null",
    "city": "string | null",
    "zone_id": "string | null"
  },
  "stats": {
    "total_requests": "number",
    "avg_rating": "number | null"
  },
  "created_at": "datetime"
}

C) service_agents collection
Purpose

Stores agents, skills, coverage, schedules, and assignment logic.

{
  "_id": "ObjectId",
  "agent_code": "string",
  "name": "string",
  "department": "string",
  "skills": ["string"],
  "coverage": {
    "zone_ids": ["string"],
    "geo_fence": {
      "type": "Polygon",
      "coordinates": [[[ "number", "number" ]]]
    }
  },
  "schedule": {
    "timezone": "string",
    "shifts": [
      { "day": "string", "start": "HH:MM", "end": "HH:MM" }
    ],
    "on_call": "boolean"
  },
  "contacts": { "phone": "string | null" },
  "roles": ["string"],
  "active": "boolean",
  "created_at": "datetime"
}

D) performance_logs collection
Purpose

Immutable audit trail and KPI computation.

{
  "_id": "ObjectId",
  "request_id": "ObjectId",
  "event_stream": [
    {
      "type": "string",
      "by": {
        "actor_type": "string",
        "actor_id": "string"
      },
      "at": "datetime",
      "meta": {}
    }
  ],
  "computed_kpis": {
    "resolution_minutes": "number",
    "sla_target_hours": "number",
    "sla_state": "string",
    "escalation_count": "number",
    "breach_reason": "string | null"
  },
  "citizen_feedback": {
    "rating": "number",
    "reason_codes": ["string"],
    "comment": "string | null",
    "dispute_flag": "boolean",
    "submitted_at": "datetime"
  }
}

E) geo_feeds collection
Purpose

Stores GeoJSON outputs for map visualizations.

{
  "_id": "ObjectId",
  "feed_name": "string",
  "generated_at": "datetime",
  "filters": {},
  "geojson": {
    "type": "FeatureCollection",
    "features": []
  },
  "aggregation": {
    "method": "string",
    "weight_formula": "string",
    "tile_hint": "string"
  }
}

3) APIs

POST /requests/

GET /requests/{request_id}

PATCH /requests/{request_id}/transition

POST /requests/{request_id}/auto-assign

POST /requests/{request_id}/rating

GET /analytics/kpis

GET /analytics/geofeeds/heatmap

4) SLA monitoring scheduler

Background job evaluates:

elapsed time

SLA thresholds

escalation rules

KPI updates

5) Comment threading (without extra collection)

Use performance_logs.event_stream with:

{
  "type": "comment",
  "meta": {
    "comment_id": "string",
    "parent_comment_id": "string | null",
    "message": "string"
  }
}

6) Storage vs Computation

service_requests → operational state

performance_logs → immutable history + KPIs

geo_feeds → cached analytics

7) Running the service

Install dependencies:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set environment variables (copy the example):

```
cp .env.example .env
```

Start MongoDB locally or point `MONGO_URI` to your cluster, then run:

```
uvicorn app.main:app --reload
```

Example requests:

```
curl -X POST http://localhost:8000/requests/ \\
  -H \"Content-Type: application/json\" \\
  -H \"Idempotency-Key: demo-1\" \\
  -d '{\n    \"citizen_ref\": {\"citizen_id\": null, \"anonymous\": true, \"contact_channel\": \"none\"},\n    \"category\": \"pothole\",\n    \"description\": \"Large pothole near downtown\",\n    \"location\": {\"type\": \"Point\", \"coordinates\": [-74.0, 40.71], \"address_hint\": \"Main St\"}\n  }'\n```
