from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResult
from app.schemas.common import ApiResponse
from app.schemas.user import UserPublic

router = APIRouter()


@router.post("/login", response_model=ApiResponse[LoginResult])
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> ApiResponse[LoginResult]:
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not user.is_active or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    return ApiResponse(
        message="登录成功",
        data=LoginResult(
            access_token=create_access_token(str(user.id), user.role.value),
            user=UserPublic.model_validate(user),
        ),
    )


@router.get("/me", response_model=ApiResponse[UserPublic])
def me(current_user: User = Depends(get_current_user)) -> ApiResponse[UserPublic]:
    return ApiResponse(data=UserPublic.model_validate(current_user))


@router.post("/logout", response_model=ApiResponse[None])
def logout(_: User = Depends(get_current_user)) -> ApiResponse[None]:
    # 当前采用短期无状态令牌；客户端删除令牌即退出。
    return ApiResponse(message="已退出登录")

