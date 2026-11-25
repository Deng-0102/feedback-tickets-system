from fastapi import APIRouter

from app.api.routes import analysis, auth, health, tickets, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["系统"])
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["工单"])
# 3 号智能分析模块：工单维度 /tickets/{id}/analysis，以及提交页预览 /analysis/preview
api_router.include_router(analysis.router, prefix="/tickets", tags=["智能分析"])
api_router.include_router(analysis.preview_router, prefix="/analysis", tags=["智能分析"])
