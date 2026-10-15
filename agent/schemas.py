"""Pydantic schemas for the Storybook Agent.

Implements all data models defined in SPEC.md Section 6:
- CharacterBible
- Page
- Story (with strict 5-page validation)
- CheckResult
"""

from typing import Dict, List, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CharacterBible(BaseModel):
    """Character appearance and visual identity specification."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., description="Character name")
    age_description: str = Field(
        ...,
        description="Character's age description, e.g. 'about 7 years old'",
    )
    hair: str = Field(..., description="Hair style and color")
    eyes: str = Field(..., description="Eye appearance and color")
    skin_tone: str = Field(..., description="Skin tone")
    outfit: str = Field(
        ...,
        description="Exact clothes and colors, consistent across all illustrations",
    )
    signature_item: str = Field(
        ...,
        description="Unique signature item, e.g. 'small brass lantern'",
    )
    art_style: str = Field(
        ...,
        description="Visual style guideline, e.g. 'soft watercolor, warm palette'",
    )
    palette: Dict[str, str] = Field(
        ...,
        description=(
            "Hex colour codes for each character element. "
            "Keys: hair, skin, eyes, coat, overalls, boots, ribbon, item. "
            "Values: exact #RRGGBB hex codes that match the outfit text."
        ),
    )

    def to_prompt_string(self) -> str:
        """Format character bible details consistently for image prompts."""
        return (
            f"Character: {self.name}, {self.age_description}. "
            f"Hair: {self.hair}. Eyes: {self.eyes}. Skin tone: {self.skin_tone}. "
            f"Outfit: {self.outfit}. Signature item: {self.signature_item}. "
            f"Art style: {self.art_style}."
        )


class Page(BaseModel):
    """A single page of the children's storybook."""

    model_config = ConfigDict(str_strip_whitespace=True)

    page_no: int = Field(
        ...,
        ge=1,
        le=5,
        description="Page sequence number (1 to 5)",
    )
    title: str = Field(..., description="Short page title")
    text: str = Field(
        ...,
        description="Page story text (typically 2-3 simple sentences)",
    )
    scene_description: str = Field(
        ...,
        description="Scene description for image generation (no character appearance details here)",
    )
    pose: Literal["standing", "crouch", "hop", "arms_up", "sit"] = Field(
        ...,
        description=(
            "Character pose for this page. Choose the pose that best fits the "
            "scene action: 'standing' (neutral/calm), 'crouch' (looking at ground/hiding), "
            "'hop' (jumping/crossing something), 'arms_up' (excited/surprised/waving), "
            "'sit' (resting/reading/relaxed)."
        ),
    )


class Story(BaseModel):
    """Complete children's storybook structure."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., description="Storybook title")
    character: CharacterBible = Field(
        ...,
        description="Character bible defining the main character",
    )
    pages: List[Page] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="List of story pages (must be exactly 5 pages)",
    )

    @field_validator("pages")
    @classmethod
    def validate_exactly_five_pages(cls, v: List[Page]) -> List[Page]:
        """Validate that the story contains exactly 5 pages covering page numbers 1 to 5."""
        if len(v) != 5:
            raise ValueError(f"Story must contain exactly 5 pages, received {len(v)}.")

        page_numbers = [p.page_no for p in v]
        if sorted(page_numbers) != [1, 2, 3, 4, 5]:
            raise ValueError(
                f"Story pages must contain page numbers 1 through 5, got: {page_numbers}."
            )
        return v


class CheckResult(BaseModel):
    """Consistency checker output evaluating visual character match."""

    model_config = ConfigDict(str_strip_whitespace=True)

    score: int = Field(
        ...,
        ge=1,
        le=10,
        description="Consistency score from 1 to 10 (>= 7 is considered passing)",
    )
    issues: List[str] = Field(
        default_factory=list,
        description="List of detected inconsistencies or visual issues",
    )
