from fastapi import APIRouter, HTTPException
from app.schemas.agent import AgentCreate, AgentUpdate, AgentOut
from app.services.agents_service import (
    list_agents,
    create_agent,
    update_agent,
    toggle_agent_active,
    delete_agent,
)

router = APIRouter(prefix="/admin/agents", tags=["Admin Agents"])


@router.get("/", response_model=list[AgentOut])
async def get_all():
    return await list_agents()


@router.post("/", response_model=AgentOut)
async def create(data: AgentCreate):
    return await create_agent(data)


@router.patch("/{agent_id}", response_model=AgentOut)
async def update(agent_id: str, patch: AgentUpdate):
    updated = await update_agent(agent_id, patch.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Agent not found")
    return updated


@router.post("/{agent_id}/toggle", response_model=AgentOut)
async def toggle(agent_id: str):
    agent = await toggle_agent_active(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{agent_id}")
async def delete(agent_id: str):
    ok = await delete_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"success": True}
