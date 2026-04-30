from collections.abc import Callable
from enum import Enum
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.api.errors import make_api_error


class DemoRole(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


class AuthContext(BaseModel):
    subject: str
    role: DemoRole


def get_demo_auth_context(
    x_demo_principal: Annotated[str | None, Header(alias="X-Demo-Principal")] = None,
    x_demo_role: Annotated[str | None, Header(alias="X-Demo-Role")] = None,
) -> AuthContext:
    if x_demo_role is None or not x_demo_role.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=make_api_error(
                code="missing_role",
                message="Missing X-Demo-Role header.",
            ),
        )

    role_value = x_demo_role.strip().lower()
    try:
        role = DemoRole(role_value)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=make_api_error(
                code="invalid_role",
                message="Invalid demo role.",
                details={"allowed_roles": [role.value for role in DemoRole]},
            ),
        ) from error

    subject = (
        x_demo_principal.strip()
        if x_demo_principal and x_demo_principal.strip()
        else "demo-user"
    )
    return AuthContext(subject=subject, role=role)


def require_roles(*allowed_roles: DemoRole) -> Callable[[AuthContext], AuthContext]:
    allowed = set(allowed_roles)
    allowed_role_values = sorted(role.value for role in allowed)

    def dependency(
        auth_context: Annotated[AuthContext, Depends(get_demo_auth_context)],
    ) -> AuthContext:
        if auth_context.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=make_api_error(
                    code="forbidden",
                    message="Role is not allowed for this operation.",
                    details={
                        "role": auth_context.role.value,
                        "required_roles": allowed_role_values,
                    },
                ),
            )
        return auth_context

    return dependency
