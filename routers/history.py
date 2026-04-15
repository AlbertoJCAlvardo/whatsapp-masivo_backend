from fastapi import APIRouter, HTTPException, Depends
from services.bigquery_service import get_bigquery_service
from routers.messages import verify_token

router = APIRouter(prefix="/history", tags=["history"], dependencies=[Depends(verify_token)])

@router.get("/campaigns")
async def get_campaign_history():
    """Obtiene el historial de campañas masivas (agrupadas por hora)."""
    try:
        bq_service = get_bigquery_service()
        stats = bq_service.get_campaign_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
