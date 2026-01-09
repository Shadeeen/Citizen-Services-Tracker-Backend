# Cst

1) System concept (what the backend must enforce)

CST is not just CRUD tickets. It must enforce:

Strict workflow/state machine: new → triaged → assigned → in_progress → resolved → closed with rule-based transitions and mandatory fields per transition. 

Final+Project+Guidelines+1st+20…

SLA policy selection + escalation rules per category/zone/priority with automated escalation steps. 

Final+Project+Guidelines+1st+20…

Duplicate detection and merge into a master request. 

Final+Project+Guidelines+1st+20…

Geo-enabled requests stored as GeoJSON with 2dsphere index, used for live heatmap/clustering and zone summaries. 

Final+Project+Guidelines+1st+20…

Assignment policy based on zone + skills + workload + availability (on shift). 

Final+Project+Guidelines+1st+20…

Immutable audit/performance logs (event stream) used to compute KPIs like resolution time, SLA state, escalation count, etc. 

Final+Project+Guidelines+1st+20…

2) Core database collections (MongoDB)

The project explicitly uses these collections:

service_requests (main requests)

citizens (profiles and preferences)

service_agents (agents/teams)

performance_logs (audit/event stream + computed KPIs + ratings)

geo_feeds (GeoJSON map feeds/snapshots) 

Final+Project+Guidelines+1st+20…

Below are recommended full field sets (aligned to the provided sample schemas and required features). 

Final+Project+Guidelines+1st+20…

A) service_requests collection
Purpose

The single source of truth for each request (ticket), including: citizen reference, classification, workflow state, SLA policy, timestamps, geo-location, duplicates, assignment, evidence, and internal notes. 

Final+Project+Guidelines+1st+20…

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


This matches the required capabilities and sample structure. 

Final+Project+Guidelines+1st+20…

Required indexes

request_id unique index

location 2dsphere index (GeoJSON Point) 

Final+Project+Guidelines+1st+20…

Common query indexes (for filters/pagination):

status, priority, category, location.zone_id, timestamps.created_at, timestamps.updated_at

Duplicate lookup: duplicates.master_request_id, duplicates.is_master

Key logic rules for service_requests
1) Create request (idempotent)

API: POST /requests/ must support idempotency key (same key = return same created request, no duplicates created). 

Final+Project+Guidelines+1st+20…

On create:

set status = new

set timestamps: created_at, updated_at

compute zone_id from coordinates (zone mapping method is your implementation, but the field must be stored)

select priority (initial default based on category/tags; staff can adjust in triage)

select sla_policy based on (category + zone + priority) and store it inside request

emit performance log event: created

2) Duplicate detection + merge

On create (and optionally on triage), detect duplicates using a rule like:

same category (or compatible)

distance within radius (e.g., 20–50m) using geospatial query

time window (e.g., last 24–72h)

similar description (optional)

If duplicate found:

choose a master request (existing master or oldest)

new request becomes non-master:

duplicates.is_master=false

duplicates.master_request_id = <master_request_id>

master request updates:

add duplicate request_id into duplicates.linked_duplicates[]

Ensure GET /requests/{request_id} returns master + linked duplicates list. 

Final+Project+Guidelines+1st+20…

3) Workflow/state machine transitions

API: PATCH /requests/{request_id}/transition must validate:

current state

requested next state is allowed by rules

mandatory fields exist (in request or in the transition payload)

every successful transition:

updates status, workflow.current_state, workflow.allowed_next

sets the correct timestamp (e.g., triaged_at, assigned_at, etc.)

updates updated_at

writes a corresponding event to performance_logs.event_stream 

Final+Project+Guidelines+1st+20…

Allowed transitions (strict):

new → triaged OR (optional) new → closed (if invalid/spam)

triaged → assigned OR triaged → closed

assigned → in_progress (when agent starts work)

in_progress → resolved

resolved → closed (after review and/or citizen feedback window)

Mandatory data per transition (recommended minimum):

new → triaged requires: confirmed category, priority, sla_policy, zone_id

triaged → assigned requires: assignment.assigned_agent_id set and assigned_at timestamp

assigned → in_progress requires: milestone event “arrived” or “work_started” (stored in logs), set in_progress_at

in_progress → resolved requires: resolution evidence or checklist completion (store as evidence + milestone log), set resolved_at

resolved → closed requires: staff closure action, set closed_at

(These align with the milestone and lifecycle requirements.) 

Final+Project+Guidelines+1st+20…

4) Manual escalation endpoint

API: POST /requests/{request_id}/escalate

Creates an event in performance logs: sla_escalation with who triggered it (staff/system) and reason.

Updates computed SLA state.

B) citizens collection
Purpose

Stores citizen profile (or limited profile if anonymous is allowed), verification state, contact info, preferences (privacy + notifications), and stats summary. 

Final+Project+Guidelines+1st+20…

Document fields
{
  "_id": "ObjectId",

  "full_name": "string | null",

  "verification": {
    "state": "string enum: unverified|verified",
    "method": "string (e.g., otp_stub)",
    "verified_at": "datetime | null"
  },

  "contacts": {
    "email": "string | null",
    "phone": "string | null"
  },

  "preferences": {
    "preferred_contact": "string enum: email|sms|none",
    "language": "string (e.g., ar|en)",
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


Matches the sample and portal requirements. 

Final+Project+Guidelines+1st+20…

Indexes

contacts.email unique (sparse)

contacts.phone unique (sparse)

verification.state

address.zone_id

Key logic rules

Citizen can submit as:

verified/identified citizen (citizen_ref.citizen_id set)

anonymous (citizen_ref.anonymous=true, citizen_ref.citizen_id=null) 

Final+Project+Guidelines+1st+20…

POST /citizens/ supports verification flow (OTP/token can be stubbed), but store verification state anyway. 

Final+Project+Guidelines+1st+20…

GET /citizens/{citizen_id} returns profile + KPIs, but restrict sensitive fields if needed (your API design).

C) service_agents collection
Purpose

Stores teams/agents with skills, coverage zones/geofence, schedules (shifts), roles, active status, and contacts. Used by auto-assignment policy. 

Final+Project+Guidelines+1st+20…

Document fields
{
  "_id": "ObjectId",

  "agent_code": "string unique (e.g., AG-PW-07)",
  "name": "string",
  "department": "string",

  "skills": ["string (e.g., road_maintenance, asphalt, water)"],

  "coverage": {
    "zone_ids": ["string"],
    "geo_fence": {
      "type": "Polygon",
      "coordinates": [[[ "number(lon)", "number(lat)" ]]]
    }
  },

  "schedule": {
    "timezone": "string (e.g., Asia/Jerusalem)",
    "shifts": [
      { "day": "string enum Mon..Sun", "start": "HH:MM", "end": "HH:MM" }
    ],
    "on_call": "boolean"
  },

  "contacts": { "phone": "string | null" },

  "roles": ["string (e.g., agent)"],
  "active": "boolean",

  "created_at": "datetime"
}


Matches the sample and assignment requirements. 

Final+Project+Guidelines+1st+20…

Indexes

agent_code unique

coverage.zone_ids

(optional) coverage.geo_fence 2dsphere if you query agents by polygon containment

Key logic rules (auto assignment)

API: POST /requests/{request_id}/auto-assign
Assignment score is computed using:

Zone match: agent must cover request.location.zone_id (or contain point in geo_fence) 

Final+Project+Guidelines+1st+20…

Skill match: agent.skills must include required skill(s) derived from request category/sub_category

Availability: agent must be on shift now (based on timezone + day + shift range) OR on_call=true

Workload balancing: pick lowest workload among eligible agents

workload can be computed via counting open assigned/in_progress requests for that agent in service_requests, or from analytics cache.

When assigned:

update service_requests.assignment.assigned_agent_id

set assigned_at

transition triaged → assigned

log event assigned in performance_logs

D) performance_logs collection
Purpose

Stores the immutable audit trail (event stream) per request, plus computed KPIs and citizen feedback rating. 

Final+Project+Guidelines+1st+20…

Document fields
{
  "_id": "ObjectId",

  "request_id": "ObjectId (reference to service_requests._id)",

  "event_stream": [
    {
      "type": "string (created|triaged|assigned|milestone|sla_escalation|resolved|closed|comment|rating|...)",
      "by": {
        "actor_type": "string enum: citizen|dispatcher|agent|system",
        "actor_id": "string|ObjectId"
      },
      "at": "datetime",
      "meta": { "any": "object" }
    }
  ],

  "computed_kpis": {
    "resolution_minutes": "number | null",
    "sla_target_hours": "number",
    "sla_state": "string enum: on_time|at_risk|overdue|breached",
    "escalation_count": "number",
    "breach_reason": "string | null"
  },

  "citizen_feedback": {
    "rating": "number 1..5",
    "reason_codes": ["string"],
    "comment": "string | null",
    "dispute_flag": "boolean",
    "submitted_at": "datetime"
  }
}


Matches the sample and requirements (ratings + dispute + SLA events + KPI computation). 

Final+Project+Guidelines+1st+20…

Indexes

request_id unique (1 log doc per request) OR non-unique (if you choose 1 event per doc); the sample uses 1 doc with event_stream array. 

Final+Project+Guidelines+1st+20…

event_stream.at (optional for analytics)

KPI computation logic (must be consistent)

Compute from timestamps/events:

SLA timeline: created_at → triaged_at → assigned_at → resolved_at 

Final+Project+Guidelines+1st+20…

resolution_minutes = (resolved_at - created_at) (or closed if you define resolution at close)

sla_state:

on_time if elapsed < target

at_risk if near target (e.g., >= 80% of target or within some threshold)

overdue/breached if elapsed > target or breach_threshold_hours

escalation_count = number of sla_escalation events in event_stream

breach_reason could be derived from which step triggered, or just store "timeout" unless you implement richer reasons

E) geo_feeds collection
Purpose

Stores GeoJSON outputs for the map layer (heatmap, clustering, zone-level summaries), generated periodically or on-demand. 

Final+Project+Guidelines+1st+20…

Document fields
{
  "_id": "ObjectId",

  "feed_name": "string (e.g., open_requests_heatmap)",
  "generated_at": "datetime",

  "filters": {
    "status_in": ["string"],
    "zone_id": "string | null",
    "category_in": ["string"],
    "priority_in": ["string"] 
  },

  "geojson": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "properties": {
          "request_id": "string",
          "category": "string",
          "priority": "string",
          "weight": "number",
          "age_hours": "number"
        },
        "geometry": { "type": "Point", "coordinates": ["number(lon)", "number(lat)"] }
      }
    ]
  },

  "aggregation": {
    "method": "string (weighted_heatmap|cluster|zone_summary)",
    "weight_formula": "string (documented formula)",
    "tile_hint": "string (optional e.g., z=12)"
  }
}


Matches the sample and analytics map requirement. 

Final+Project+Guidelines+1st+20…

Geo feed generation logic

API: GET /analytics/geofeeds/heatmap must return GeoJSON with weights. 

Final+Project+Guidelines+1st+20…

Data source is service_requests filtered by open statuses: new, triaged, assigned, in_progress. 

Final+Project+Guidelines+1st+20…

Suggested weight:

priority_weight * log1p(age_hours) (exactly like the sample idea) 

Final+Project+Guidelines+1st+20…

Store the produced feed in geo_feeds for caching and reuse.

3) APIs (what each endpoint must read/write)
Service Requests

POST /requests/

writes: service_requests (+ creates corresponding performance_logs doc if not exists, add created event)

performs: validation, zone tagging, SLA selection, duplicate detection, idempotency

GET /requests/{request_id}

reads: service_requests + duplicate links + SLA state (from performance_logs.computed_kpis)

GET /requests/

filters: status/category/priority/zone/date range/merged-vs-master + pagination + sorting 

Final+Project+Guidelines+1st+20…

PATCH /requests/{request_id}/transition

enforces workflow rules + mandatory fields + logs events

POST /requests/{request_id}/escalate

adds escalation event + updates SLA state

Citizen interactions

POST /citizens/ create/verify citizen (OTP stub ok) 

Final+Project+Guidelines+1st+20…

GET /citizens/{citizen_id} profile + summary KPIs 

Final+Project+Guidelines+1st+20…

POST /requests/{request_id}/comment

requirement says citizen comments thread; simplest implementation: store as events in performance_logs.event_stream with type=comment and meta including thread/reply references.

POST /requests/{request_id}/rating

store in performance_logs.citizen_feedback + add event rating (and optionally update citizens.stats.avg_rating) 

Final+Project+Guidelines+1st+20…

Agents

POST /agents/ create agent/team 

Final+Project+Guidelines+1st+20…

GET /agents/{agent_id} workload + performance summary (computed from requests/logs) 

Final+Project+Guidelines+1st+20…

POST /requests/{request_id}/auto-assign

runs assignment policy then transitions to assigned

PATCH /requests/{request_id}/milestone

adds milestone events (arrived/work_started/resolved evidence) to performance_logs and may trigger state changes 

Final+Project+Guidelines+1st+20…

Analytics

GET /analytics/kpis backlog, SLA breach %, avg resolution, ratings 

Final+Project+Guidelines+1st+20…

GET /analytics/cohorts repeat-issue cohorts & recurrence metrics 

Final+Project+Guidelines+1st+20…

GET /analytics/agents productivity/workload analytics 

Final+Project+Guidelines+1st+20…

Use Mongo aggregations: $lookup, $facet, $bucketAuto, $geoNear, $group for multi-dimensional analytics. 

Final+Project+Guidelines+1st+20…

4) SLA monitoring scheduler (system logic)

A background scheduler (could be APScheduler, cron, or periodic job) must:

Query all open requests.

For each request:

compute elapsed hours since created_at

compare with sla_policy.target_hours and breach_threshold_hours

if an escalation step threshold is reached and not already logged:

create sla_escalation event in performance_logs.event_stream

increment computed_kpis.escalation_count

update computed_kpis.sla_state to at_risk/overdue/breached depending on time 

Final+Project+Guidelines+1st+20…

5) Minimal “comment threading” structure (without adding a new collection)

Since the guideline mentions a threaded comment experience, you can encode threading inside performance logs:

Event example:

{
  "type": "comment",
  "by": { "actor_type": "citizen", "actor_id": "ObjectId" },
  "at": "datetime",
  "meta": {
    "comment_id": "uuid/string",
    "parent_comment_id": "uuid/string | null",
    "message": "string"
  }
}


This keeps audit immutability and avoids extra collections while still supporting threads.

6) What to store vs compute (important for coding)
Store directly inside service_requests

Anything needed to render request details quickly:

status, priority, category, location, timestamps, assignment, duplicates, SLA policy, evidence, internal notes 

Final+Project+Guidelines+1st+20…

Store inside performance_logs

Immutable events + derived KPIs + rating/feedback (because it’s audit and analytics-friendly). 

Final+Project+Guidelines+1st+20…

Store inside geo_feeds

Prebuilt GeoJSON used by the map to avoid heavy repeated queries.
