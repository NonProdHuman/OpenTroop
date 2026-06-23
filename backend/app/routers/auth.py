from fastapi import APIRouter

from app.core.deps import CurrentUserDep
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserRead)
def get_me(current_user: CurrentUserDep) -> object:
    return current_user
