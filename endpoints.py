from fastapi import APIRouter

from service.daily_report_service import daily_report_service
from service.team_weekly_service import team_weekly_report_service
from service.weekly_report_service import weekly_report_service


router = APIRouter()

@router.get("/", tags=["Root"])
def read_root():
    return {"message": "Hello from FastAPI"}
  
@router.get("/daily", tags=["보고서 생성"])
async def create_daily():
  daily_report_service()
  return

@router.get("/weekly", tags=["보고서 생성"])
async def create_weekly():
  weekly_report_service()
  return

@router.get("/team-weekly", tags=["보고서 생성"])
async def create_team_weekly():
  team_weekly_report_service()
  return