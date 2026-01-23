from fastapi import APIRouter, Response, HTTPException
import httpx

router = APIRouter(prefix="/tiles", tags=["Tiles"])

@router.get("/{z}/{x}/{y}.png")
async def osm_tile(z: int, x: int, y: int):
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="Tile fetch failed")
        return Response(
            content=r.content,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=86400",
            },
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Tile proxy error")
