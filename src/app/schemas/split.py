from typing import List

from pydantic import BaseModel, Field, field_validator


class PageSplit(BaseModel):
    page: int = Field(..., description="Page number where a new part should start (1-based)")

    @field_validator("page")
    @classmethod
    def validate_page_number(cls, v):
        if v < 1:
            raise ValueError("Page number must be 1 or greater")
        return v


class SplitRequest(BaseModel):
    pages: List[PageSplit] = Field(..., description="List of page numbers where new parts start")

    @field_validator("pages")
    @classmethod
    def validate_pages_list(cls, v):
        if not v or len(v) < 1:
            raise ValueError("At least one page must be specified")
        return v


class SplitPartMetadata(BaseModel):
    filename: str
    part_number: int
    total_parts: int
