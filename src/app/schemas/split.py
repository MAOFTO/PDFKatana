from typing import List

from pydantic import BaseModel, Field, field_validator


class SplitRequest(BaseModel):
    separators: List[int] = Field(..., description="1-based page indices where new slices start.")

    @field_validator("separators")
    @classmethod
    def check_min_length(cls, v):
        if not v or len(v) < 1:
            raise ValueError("At least one separator is required.")
        return v


class SplitPartMetadata(BaseModel):
    filename: str
    part_number: int
    total_parts: int
