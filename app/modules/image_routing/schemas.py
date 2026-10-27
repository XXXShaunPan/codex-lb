from pydantic import Field, field_validator

from app.modules.shared.schemas import DashboardModel


class ImageRoutingUpdate(DashboardModel):
    host_model: str | None = Field(default=None, max_length=255)

    @field_validator("host_model")
    @classmethod
    def validate_host(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        if value and value.startswith("gpt-image-"):
            raise ValueError("The Responses host must be a text/tool model, not an image model")
        return value or None


class ImageRoutingResponse(ImageRoutingUpdate):
    resolved_host_model: str | None = None
    available_host_models: list[str] = Field(default_factory=list)
