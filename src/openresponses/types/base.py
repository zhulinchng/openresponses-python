from pydantic import BaseModel, ConfigDict


class OpenResponsesModel(BaseModel):
    """Base model for OpenResponses wire objects and forward-compatible extensions."""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        validate_assignment=True,
        ser_json_timedelta="iso8601",
    )
