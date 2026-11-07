from langgraph.graph import StateGraph, END
from schemas.models import PipelineState


def route_after_audit(state: PipelineState) -> str:
    status = state.get("status") if isinstance(state, dict) else state.status
    if status == "seo_drafting":
        return "seo_listing"
    if status == "designing":
        return "muse_designer"
    return END


def build_ultron_graph(nova_fn, muse_fn, audit_fn, seo_fn, forge_fn):
    workflow = StateGraph(PipelineState)

    workflow.add_node("nova_research", nova_fn)
    workflow.add_node("muse_designer", muse_fn)
    workflow.add_node("audit_gate", audit_fn)
    workflow.add_node("seo_listing", seo_fn)
    workflow.add_node("forge_printify", forge_fn)

    workflow.set_entry_point("nova_research")
    workflow.add_edge("nova_research", "muse_designer")
    workflow.add_edge("muse_designer", "audit_gate")

    workflow.add_conditional_edges(
        "audit_gate",
        route_after_audit,
        {
            "seo_listing": "seo_listing",
            "muse_designer": "muse_designer",
            END: END,
        },
    )

    workflow.add_edge("seo_listing", "forge_printify")
    workflow.add_edge("forge_printify", END)

    return workflow.compile()
