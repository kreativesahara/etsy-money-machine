import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from schemas.models import PipelineState

logger = logging.getLogger(__name__)


class StorageService:
    """
    Cloud-ready storage layer supporting:
    1. PostgreSQL (`DATABASE_URL`) for structured pipeline runs, audit logs, and SEO metadata,
       with automatic fallback to a local JSONL volume store (`artifacts/storage/pipeline_runs.jsonl`).
    2. S3-compatible Object Storage (MinIO locally in Docker, or AWS S3 / Cloudflare R2 / Supabase Storage in cloud)
       for raw and 4500x5400 @ 300 DPI PNG design assets.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        local_store_path: Optional[Path] = None,
        s3_enabled: bool = False,
        s3_endpoint_url: Optional[str] = None,
        s3_access_key: Optional[str] = None,
        s3_secret_key: Optional[str] = None,
        s3_bucket_name: str = "etsy-renders",
        s3_region: str = "us-east-1",
    ) -> None:
        self.database_url = database_url
        base_dir = Path(__file__).resolve().parent.parent / "artifacts" / "storage"
        self.local_store_path = Path(local_store_path) if local_store_path else (base_dir / "pipeline_runs.jsonl")
        self.local_store_path.parent.mkdir(parents=True, exist_ok=True)

        self.s3_enabled = s3_enabled
        self.s3_endpoint_url = s3_endpoint_url
        self.s3_access_key = s3_access_key
        self.s3_secret_key = s3_secret_key
        self.s3_bucket_name = s3_bucket_name
        self.s3_region = s3_region
        self._pg_reachable_cache: Optional[bool] = None

    def _pg_available(self) -> bool:
        if not self.database_url:
            return False
        if self._pg_reachable_cache is False:
            return False
        try:
            import psycopg  # noqa: F401

            return True
        except ImportError:
            return False

    def ensure_postgres_schema(self) -> bool:
        """Ensure the `pipeline_runs` table exists in PostgreSQL when `database_url` is reachable."""
        if not self._pg_available():
            return False
        sql_path = Path(__file__).resolve().parent.parent / "db" / "init" / "001_init_schema.sql"
        if not sql_path.exists():
            return False
        try:
            import psycopg

            with psycopg.connect(self.database_url, connect_timeout=1) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql_path.read_text(encoding="utf-8"))
                conn.commit()
            self._pg_reachable_cache = True
            return True
        except Exception as exc:
            self._pg_reachable_cache = False
            logger.debug("PostgreSQL schema init skipped (using local volume store fallback): %s", exc)
            return False

    def upload_asset_to_object_storage(self, file_path: Path, object_key: Optional[str] = None) -> str:
        """
        Upload a PNG file to S3/MinIO object storage if enabled; otherwise return the persistent volume URI.
        """
        path_obj = Path(file_path).resolve()
        if not self.s3_enabled or not self.s3_endpoint_url:
            return path_obj.as_uri()

        key = object_key or f"renders/{path_obj.name}"
        try:
            import boto3
            from botocore.exceptions import ClientError

            s3 = boto3.client(
                "s3",
                endpoint_url=self.s3_endpoint_url,
                aws_access_key_id=self.s3_access_key,
                aws_secret_access_key=self.s3_secret_key,
                region_name=self.s3_region,
            )
            try:
                s3.head_bucket(Bucket=self.s3_bucket_name)
            except ClientError:
                s3.create_bucket(Bucket=self.s3_bucket_name)

            s3.upload_file(
                str(path_obj),
                self.s3_bucket_name,
                key,
                ExtraArgs={"ContentType": "image/png"},
            )
            return f"s3://{self.s3_bucket_name}/{key}"
        except Exception as exc:
            logger.warning("S3/MinIO upload fell back to local volume URI: %s", exc)
            return path_obj.as_uri()

    def save_pipeline_run(self, state: PipelineState) -> Dict[str, Any]:
        """
        Persist a completed or halted PipelineState to PostgreSQL (if reachable) AND local volume JSONL.
        """
        run_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        raw_uri = None
        print_ready_uri = None
        if state.design_asset:
            raw_path = Path(state.design_asset.raw_image_path)
            print_path = Path(state.design_asset.print_ready_path)
            if raw_path.exists():
                raw_uri = self.upload_asset_to_object_storage(raw_path)
            if print_path.exists():
                print_ready_uri = self.upload_asset_to_object_storage(print_path)

        record: Dict[str, Any] = {
            "id": run_id,
            "seed_category": state.seed_category,
            "status": state.status,
            "revision_count": state.revision_count,
            "render_confidence": (
                state.audit_result.render_confidence if state.audit_result else None
            ),
            "approved": bool(state.audit_result.approved) if state.audit_result else False,
            "printify_product_id": state.printify_product_id,
            "raw_image_uri": raw_uri,
            "print_ready_uri": print_ready_uri,
            "niche_brief": state.niche_brief.model_dump() if state.niche_brief else None,
            "design_asset": state.design_asset.model_dump() if state.design_asset else None,
            "audit_result": state.audit_result.model_dump() if state.audit_result else None,
            "seo_listing": state.seo_listing.model_dump() if state.seo_listing else None,
            "storage_backend": "local_volume",
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        if self._pg_available():
            try:
                import psycopg
                from psycopg.types.json import Jsonb

                if not self.ensure_postgres_schema():
                    raise RuntimeError("PostgreSQL unreachable")
                with psycopg.connect(self.database_url, connect_timeout=1) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO public.pipeline_runs (
                                id, seed_category, status, revision_count,
                                render_confidence, approved, printify_product_id,
                                raw_image_uri, print_ready_uri,
                                niche_brief, design_asset, audit_result, seo_listing,
                                created_at, updated_at
                            ) VALUES (
                                %s, %s, %s, %s,
                                %s, %s, %s,
                                %s, %s,
                                %s, %s, %s, %s,
                                %s, %s
                            )
                            """,
                            (
                                run_id,
                                record["seed_category"],
                                record["status"],
                                record["revision_count"],
                                record["render_confidence"],
                                record["approved"],
                                record["printify_product_id"],
                                record["raw_image_uri"],
                                record["print_ready_uri"],
                                Jsonb(record["niche_brief"]) if record["niche_brief"] else None,
                                Jsonb(record["design_asset"]) if record["design_asset"] else None,
                                Jsonb(record["audit_result"]) if record["audit_result"] else None,
                                Jsonb(record["seo_listing"]) if record["seo_listing"] else None,
                                now_iso,
                                now_iso,
                            ),
                        )
                    conn.commit()
                record["storage_backend"] = "postgresql"
            except Exception as exc:
                logger.debug("PostgreSQL insert fell back to local JSONL store: %s", exc)

        # Always append a durable copy to the local/Docker volume JSONL log
        with self.local_store_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        return record

    def list_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent pipeline runs from PostgreSQL if reachable, else from local volume JSONL."""
        if self._pg_available():
            try:
                import psycopg
                from psycopg.rows import dict_row

                with psycopg.connect(
                    self.database_url, connect_timeout=3, row_factory=dict_row
                ) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT
                                id::text AS id,
                                seed_category,
                                status,
                                revision_count,
                                render_confidence::float AS render_confidence,
                                approved,
                                printify_product_id,
                                raw_image_uri,
                                print_ready_uri,
                                niche_brief,
                                design_asset,
                                audit_result,
                                seo_listing,
                                created_at::text AS created_at,
                                updated_at::text AS updated_at
                            FROM public.pipeline_runs
                            ORDER BY created_at DESC
                            LIMIT %s
                            """,
                            (limit,),
                        )
                        rows = cur.fetchall()
                        if rows:
                            return list(rows)
            except Exception as exc:
                logger.debug("PostgreSQL query fell back to local JSONL store: %s", exc)

        if not self.local_store_path.exists():
            return []
        lines = [
            line.strip()
            for line in self.local_store_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        parsed = [json.loads(line) for line in lines]
        parsed.reverse()
        return parsed[:limit]
