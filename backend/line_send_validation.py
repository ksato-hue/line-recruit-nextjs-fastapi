import re

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator


LINE_USER_ID_PATTERN = re.compile(r"U[0-9a-f]{32}")
MAX_MESSAGE_UTF16_CODE_UNITS = 5000


def utf16_code_unit_length(value: str) -> int:
    """Return the number of UTF-16 code units without counting a BOM."""
    return len(value.encode("utf-16-le")) // 2


class LineSendRequest(BaseModel):
    """Strict request boundary for the manual LINE push endpoint."""

    model_config = ConfigDict(extra="forbid", strict=True)

    line_user_id: StrictStr
    message: StrictStr

    @field_validator("line_user_id")
    @classmethod
    def validate_line_user_id(cls, value: str) -> str:
        if LINE_USER_ID_PATTERN.fullmatch(value) is None:
            raise ValueError("line_user_id must match the LINE user ID format")
        return value

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must contain non-whitespace text")
        try:
            length = utf16_code_unit_length(value)
        except UnicodeEncodeError:
            raise ValueError("message contains invalid Unicode") from None
        if length > MAX_MESSAGE_UTF16_CODE_UNITS:
            raise ValueError(
                f"message must be at most {MAX_MESSAGE_UTF16_CODE_UNITS} UTF-16 code units"
            )
        return value
