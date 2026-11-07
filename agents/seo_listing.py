from openai import OpenAI
from schemas.models import EtsySEOListing, PipelineState

AI_PRODUCTION_DISCLOSURE = (
    "\n\n---\nTransparency & Production Disclosure: Original graphic artwork in this design was "
    "created with AI assistance and curated by our studio. Each item is printed to order with our "
    "production partner (Printify) to ensure vibrant, long-lasting print quality."
)


def run_seo_listing_node(state: PipelineState, openai_client: OpenAI) -> PipelineState:
    if isinstance(state, dict):
        state = PipelineState(**state)

    brief = state.niche_brief
    if brief is None:
        raise ValueError("SEO Listing node requires a populated NicheBrief.")

    completion = openai_client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an Etsy SEO Specialist. Write a high-converting 140-character max title, "
                    "a warm buyer-focused product description (including a transparent note that the original artwork "
                    "was created with AI assistance and printed to order with our production partner), "
                    "and exactly 13 long-tail search tags where EVERY tag is 20 characters or fewer."
                ),
            },
            {
                "role": "user",
                "content": f"Niche Brief: {brief.model_dump_json()}",
            },
        ],
        response_format=EtsySEOListing,
    )

    seo = completion.choices[0].message.parsed
    if "production partner" not in seo.description.lower() and "ai" not in seo.description.lower():
        seo.description = f"{seo.description.rstrip()}{AI_PRODUCTION_DISCLOSURE}"
    seo.ai_disclosure_included = True

    state.seo_listing = seo
    state.status = "fabricating"
    return state
