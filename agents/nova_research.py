import httpx
from openai import OpenAI
from schemas.models import NicheBrief, PipelineState

ETSY_BASE_URL = "https://api.etsy.com/v3/application"

BLACKLISTED_TRADEMARK_TERMS = {
    "disney",
    "marvel",
    "star wars",
    "taylor swift",
    "eras tour",
    "nike",
    "sanrio",
    "hello kitty",
    "pokemon",
    "nintendo",
    "harry potter",
    "barbie",
}


def is_trademark_safe(text: str) -> bool:
    """Screen candidate phrases and niche titles against blacklisted trademark terms."""
    lowered = text.lower()
    return not any(term in lowered for term in BLACKLISTED_TRADEMARK_TERMS)


def fetch_trending_etsy_listings(api_key: str, query: str, limit: int = 25) -> list[dict]:
    """`api_key` is the full x-api-key value, i.e. 'keystring:shared_secret'."""
    headers = {"x-api-key": api_key}
    params = {"keywords": query, "limit": limit, "sort_on": "score"}
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(f"{ETSY_BASE_URL}/listings/active", headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = [
        {
            "title": item.get("title"),
            "tags": item.get("tags", []),
            "favorites": item.get("num_favorers", 0),
            "views": item.get("views", 0),
        }
        for item in data.get("results", [])
    ]
    results.sort(key=lambda x: x.get("favorites", 0), reverse=True)
    return results


def run_nova_research_node(
    state: PipelineState,
    openai_client: OpenAI,
    etsy_api_key: str,
) -> PipelineState:
    if isinstance(state, dict):
        state = PipelineState(**state)

    listings = fetch_trending_etsy_listings(etsy_api_key, state.seed_category)

    completion = openai_client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Nova, Lead Market Researcher for an Etsy Print-on-Demand studio. "
                    "Analyze top-performing Etsy listings and extract a high-converting, original NicheBrief. "
                    "Never copy copyrighted characters or trademarked slogans; synthesize original hobby/lifestyle mashups."
                ),
            },
            {
                "role": "user",
                "content": f"Seed Category: {state.seed_category}\nTop Etsy Listings Data:\n{listings}",
            },
        ],
        response_format=NicheBrief,
    )

    brief = completion.choices[0].message.parsed
    if not is_trademark_safe(f"{brief.niche_name} {brief.phrase_on_product}"):
        raise ValueError(
            f"Generated NicheBrief failed trademark safety screen: '{brief.phrase_on_product}'"
        )

    state.niche_brief = brief
    state.status = "designing"
    return state
