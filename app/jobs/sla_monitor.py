from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict

from app.repositories.performance_logs import PerformanceLogRepository
from app.repositories.requests import ServiceRequestRepository
from app.services.sla import compute_sla_state


async def _process_request(request: Dict[str, Any]) -> None:
    performance_log = await PerformanceLogRepository.get_by_request_oid(
        request["_id"]
    )
    if not performance_log:
        return
    kpis = performance_log["computed_kpis"]
    computed = compute_sla_state(
        request["timestamps"]["created_at"],
        request["sla_policy"],
        kpis.get("escalation_count", 0),
    )
    escalation_steps = sorted(
        request["sla_policy"].get("escalation_steps", []),
        key=lambda step: step["after_hours"],
    )
    escalation_count = kpis.get("escalation_count", 0)
    for index, step in enumerate(escalation_steps, start=1):
        if computed["elapsed_hours"] >= step["after_hours"] and escalation_count < index:
            escalation_count = index
            await PerformanceLogRepository.append_event(
                request["_id"],
                {
                    "type": "sla_escalation",
                    "by": {"actor_type": "system", "actor_id": "cst"},
                    "at": datetime.utcnow(),
                    "meta": {"action": step["action"], "after_hours": step["after_hours"]},
                },
            )
    kpis.update(
        {
            "sla_target_hours": computed["target_hours"],
            "sla_state": computed["sla_state"],
            "breach_reason": computed["breach_reason"],
            "escalation_count": escalation_count,
        }
    )
    await PerformanceLogRepository.update_kpis(request["_id"], kpis)


async def sla_monitor_loop(interval_seconds: int, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        open_requests = await ServiceRequestRepository.find_open_requests()
        for request in open_requests:
            await _process_request(request)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue
