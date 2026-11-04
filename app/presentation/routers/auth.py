"""Authentication and registration router."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.application.dtos import (
    AuthenticateUserCommand,
    RegisterUserCommand,
)
from app.application.ports.services.token_service import TokenServicePort
from app.application.use_cases.auth import (
    AuthenticateUserUseCase,
    RegisterUserUseCase,
)
from app.presentation.dependencies import provide
from app.presentation.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    req: RegisterUserRequest,
    use_case: Annotated[RegisterUserUseCase, Depends(provide(RegisterUserUseCase))],
    token_service: Annotated[
        TokenServicePort,
        Depends(provide(TokenServicePort)),
    ],
) -> AuthResponse:
    user = use_case.execute(
        RegisterUserCommand(
            email=req.email,
            password=req.password,
            display_name=req.display_name,
            age=req.age,
            plan_id=req.plan_id,
            birth_date=req.birth_date,
            blocked_genres=tuple(req.blocked_genres),
        )
    )
    if user.user_id is None:
        raise RuntimeError("Registered user is missing its persisted ID.")
    return AuthResponse(
        access_token=token_service.create_access_token(
            user_id=user.user_id, is_admin=user.is_admin
        ),
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
def login(
    req: LoginRequest,
    use_case: Annotated[
        AuthenticateUserUseCase, Depends(provide(AuthenticateUserUseCase))
    ],
) -> AuthResponse:
    result = use_case.execute(
        AuthenticateUserCommand(email=req.email, password=req.password)
    )
    return AuthResponse(
        access_token=result.access_token,
        user=UserResponse.model_validate(result.user),
    )


__all__ = ["router"]
