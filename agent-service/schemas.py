from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

Category = Literal["processor", "motherboard", "gpu", "ram", "ps", "ss", "psu", "cabinet", "cooling"]

class RouteDecision(BaseModel):  # Supervisor
    route: Literal["ARCHITECT", "COMPARATOR", "END"]

class BuildItem(BaseModel):
    category: Category
    id: str = Field(min_length=1)

class DraftBuild(BaseModel):  # Architect
    reply: str = Field(min_length=1)
    build: list[BuildItem]
    budget: float | None = Field(default=None, ge=0, description="The maximum budget number stated by the user (e.g. 60000), or null if not mentioned")

    @field_validator("build")
    @classmethod
    def no_duplicate_ids(cls, items):
        ids = [i.id for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError("the same part id appears twice")
        return items

class Critique(BaseModel):  # Critic
    approved: bool
    issues: list[str]
    reply: str

    @model_validator(mode="after")
    def rejection_needs_a_reason(self):
        if not self.approved and not self.issues:
            raise ValueError("a rejected build must list at least one issue")
        return self

class ComponentReview(BaseModel):
    component: str
    rating: str
    pros: list[str]
    cons: list[str]
    summary: str

class Reviews(BaseModel):  # Reviewer
    reviews: list[ComponentReview]

class ComparisonData(BaseModel):
    headers: list[str] = Field(min_length=2)
    rows: list[list[str]]
    verdict: str

    @model_validator(mode="after")
    def rows_match_headers(self):
        if any(len(r) != len(self.headers) for r in self.rows):
            raise ValueError("every row needs one cell per header")
        return self

class Comparison(BaseModel):  # Comparator
    comparisonData: ComparisonData
    reply: str
