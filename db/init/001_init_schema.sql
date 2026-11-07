-- PostgreSQL Schema for Autonomous Etsy Print-on-Demand (POD) Multi-Agent Pipeline
-- Follows Supabase Postgres Best Practices (UUID PKs, TIMESTAMPTZ, JSONB, targeted B-Tree & GIN indexes)

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.pipeline_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    seed_category text NOT NULL,
    status text NOT NULL CHECK (
        status IN (
            'researching',
            'designing',
            'auditing',
            'seo_drafting',
            'fabricating',
            'completed',
            'halted',
            'published'
        )
    ),
    revision_count integer NOT NULL DEFAULT 0 CHECK (revision_count >= 0),
    render_confidence numeric(4, 3) CHECK (render_confidence >= 0.0 AND render_confidence <= 1.0),
    approved boolean NOT NULL DEFAULT false,
    printify_product_id text,
    raw_image_uri text,
    print_ready_uri text,
    niche_brief jsonb,
    design_asset jsonb,
    audit_result jsonb,
    seo_listing jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Index for dashboard queries filtering by status and ordering by newest runs
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status_created_at
    ON public.pipeline_runs (status, created_at DESC);

-- Partial index for fast lookup by Printify product ID during one-click handoff/approval
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_printify_product_id
    ON public.pipeline_runs (printify_product_id)
    WHERE printify_product_id IS NOT NULL;

-- GIN index for querying inside SEO tags and niche brief JSONB payloads
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_seo_listing_gin
    ON public.pipeline_runs USING gin (seo_listing);
