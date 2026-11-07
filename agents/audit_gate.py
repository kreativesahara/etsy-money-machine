import base64
from pathlib import Path
from openai import OpenAI
from schemas.models import AuditResult, PipelineState


def run_audit_gate_node(
    state: PipelineState,
    openai_client: OpenAI,
    min_confidence: float = 0.75,
) -> PipelineState:
    if isinstance(state, dict):
        state = PipelineState(**state)

    if state.design_asset is None or state.niche_brief is None:
        raise ValueError("Audit Gate requires both design_asset and niche_brief in PipelineState.")

    img_b64 = base64.b64encode(Path(state.design_asset.raw_image_path).read_bytes()).decode("utf-8")
    expected_phrase = state.niche_brief.phrase_on_product

    completion = openai_client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Quality Audit Gate for an automated Print-on-Demand pipeline. "
                    "Inspect the artwork carefully for exact spelling, edge clipping, and commercial print readiness."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Verify that the text in this graphic spells '{expected_phrase}' "
                            f"accurately and score render_confidence."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                ],
            },
        ],
        response_format=AuditResult,
    )

    audit = completion.choices[0].message.parsed
    audit.approved = (
        audit.render_confidence >= min_confidence
        and audit.spelling_verified
        and audit.transparent_background_clean
        and audit.trademark_safe
    )
    state.audit_result = audit

    if audit.approved:
        state.status = "seo_drafting"
    elif state.revision_count < 2:
        state.revision_count += 1
        state.status = "designing"
    else:
        state.status = "halted"

    return state
