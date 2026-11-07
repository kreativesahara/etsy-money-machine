from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class NicheBrief(BaseModel):
    niche_name: str = Field(..., description="Short name, e.g., 'In My Garden Era Floral'")
    target_persona: str = Field(..., description="Buyer persona, e.g., 'Book club & gardening enthusiasts'")
    aesthetic_style: str = Field(
        ...,
        description="Visual style, e.g., 'Cozy watercolor botanical with retro serif typography'",
    )
    phrase_on_product: str = Field(..., description="Exact text to render on the product")
    seed_keywords: List[str] = Field(..., description="Proven high-velocity search terms from Etsy")
    product_category: Literal["apparel", "candle", "portrait", "mug", "tote"] = "apparel"


class DesignAsset(BaseModel):
    design_title: str
    prompt_used: str
    raw_image_path: str
    print_ready_path: str
    width_px: int = 4500
    height_px: int = 5400
    dpi: int = 300


class AuditResult(BaseModel):
    approved: bool
    render_confidence: float = Field(..., ge=0.0, le=1.0, description="0.0 to 1.0 confidence score")
    spelling_verified: bool = Field(..., description="True if text on image matches phrase_on_product")
    transparent_background_clean: bool
    trademark_safe: bool
    critique_notes: str


class EtsySEOListing(BaseModel):
    title: str = Field(..., max_length=140)
    description: str
    tags: List[str] = Field(..., min_length=1, max_length=13)
    ai_disclosure_included: bool = True

    @field_validator("tags")
    @classmethod
    def validate_etsy_tags(cls, tags: List[str]) -> List[str]:
        cleaned = []
        for tag in tags[:13]:
            t = tag.strip()
            if len(t) > 20:
                raise ValueError(f"Etsy tag '{t}' exceeds 20 characters ({len(t)} chars).")
            cleaned.append(t)
        return cleaned


class PipelineState(BaseModel):
    seed_category: str
    store_id: str = "store_1"
    niche_brief: Optional[NicheBrief] = None
    design_asset: Optional[DesignAsset] = None
    audit_result: Optional[AuditResult] = None
    seo_listing: Optional[EtsySEOListing] = None
    printify_product_id: Optional[str] = None
    revision_count: int = 0
    status: Literal[
        "researching",
        "designing",
        "auditing",
        "seo_drafting",
        "fabricating",
        "completed",
        "halted",
    ] = "researching"
