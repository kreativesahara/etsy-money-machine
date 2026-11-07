import pytest
from pydantic import ValidationError
from schemas.models import EtsySEOListing


def test_valid_seo_listing_13_tags_and_140_char_title():
    tags = [
        "in my garden era",
        "book club babe",
        "soft girl shirt",
        "garden gift",
        "coffee lover tee",
        "botanical floral",
        "cottagecore shirt",
        "plant mom gift",
        "reading club tee",
        "cozy bookish gift",
        "retro wildflower",
        "floral graphic tee",
        "gardener shirt",
    ]
    assert len(tags) == 13
    assert all(len(t) <= 20 for t in tags)

    title = (
        "In My Garden Era Shirt | Cozy Botanical Book Club Tee | "
        "Cottagecore Plant Lover Gift | Retro Floral Gardening Sweatshirt"
    )
    assert len(title) <= 140

    listing = EtsySEOListing(
        title=title,
        description="Created with AI assistance and printed with our production partner Printify.",
        tags=tags,
    )
    assert len(listing.tags) == 13
    assert listing.ai_disclosure_included is True


def test_seo_rejects_tag_exceeding_20_characters():
    with pytest.raises(ValidationError) as exc_info:
        EtsySEOListing(
            title="Valid Short Etsy Title",
            description="Valid description",
            tags=["this tag is way over twenty characters long"],
        )
    assert "exceeds 20 characters" in str(exc_info.value)


def test_seo_rejects_title_exceeding_140_characters():
    long_title = "A" * 141
    with pytest.raises(ValidationError):
        EtsySEOListing(
            title=long_title,
            description="Valid description",
            tags=["valid tag"],
        )


def test_seo_truncates_or_limits_to_13_tags():
    fourteen_valid_tags = [f"tag number {i}" for i in range(1, 15)]
    with pytest.raises(ValidationError):
        EtsySEOListing(
            title="Valid Etsy Title",
            description="Valid description",
            tags=fourteen_valid_tags,
        )
