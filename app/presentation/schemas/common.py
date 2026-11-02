"""Common presentation schemas."""

from pydantic import BaseModel, ConfigDict


class ActionSuccessResponse(BaseModel):
    """Generic operation success response."""

    model_config = ConfigDict(from_attributes=True)

    success: bool = True


__all__ = ["ActionSuccessResponse"]
