"""Authentication and registration router."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.application.dtos import (
    AuthenticateUserCommand,
    RegisterUserCommand,
)
from app.application.dtos.auth_dtos import AuthResult
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
@router.post(
    "/cadastrar",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def register(
    req: RegisterUserRequest,
    use_case: Annotated[RegisterUserUseCase, Depends(provide(RegisterUserUseCase))],
    token_service: Annotated[
        TokenServicePort | None,
        Depends(provide(TokenServicePort)),
    ] = None,
) -> AuthResponse:
    user = use_case.execute(
        RegisterUserCommand(
            email=req.email,
            password=req.password,
            display_name=req.display_name,
            age=req.age,
            plan_id=req.plan_id,
            birth_date=req.birth_date,
        )
    )
    token = ""
    if token_service is not None and user.user_id is not None:
        token = token_service.create_access_token(
            user_id=user.user_id, is_admin=user.is_admin
        )
    return AuthResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
@router.post("/entrar", response_model=AuthResponse, include_in_schema=False)
def login(
    req: LoginRequest,
    use_case: Annotated[
        AuthenticateUserUseCase, Depends(provide(AuthenticateUserUseCase))
    ],
) -> AuthResponse:
    result = use_case.execute(
        AuthenticateUserCommand(email=req.email, password=req.password)
    )
    if isinstance(result, AuthResult):
        user = result.user
        token = result.access_token
    else:
        user = result
        token = ""
    return AuthResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


__all__ = ["router"]
