from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.user import UserPublic

router = APIRouter()


@router.get("", response_model=ApiResponse[list[UserPublic]])
def list_users(
    _: User = Depends(require_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> ApiResponse[list[UserPublic]]:
    users = db.scalars(select(User).order_by(User.id)).all()
    return ApiResponse(data=[UserPublic.model_validate(item) for item in users])

