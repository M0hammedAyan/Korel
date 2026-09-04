"""Partition anomalies and audit tables by month for high-volume scalability.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-26

This migration:
  1. Converts anomalies table to range-partitioned by created_at (monthly)
  2. Converts audit table to range-partitioned by created_at (monthly)
  3. Creates initial partitions for the next 6 months
  4. Adds indexes optimized for time-range queries
  5. Creates a function to auto-create future partitions

NOTE: This migration only runs on PostgreSQL. SQLite does not support partitioning.
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timedelta

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def _generate_monthly_partitions(table: str, months_ahead: int = 6) -> list:
    """Generate CREATE TABLE statements for monthly partitions."""
    statements = []
    now = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    for i in range(-1, months_ahead):  # Start from previous month
        start = now + timedelta(days=32 * i)
        start = start.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)

        partition_name = f"{table}_y{start.year}m{start.month:02d}"
        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")

        statements.append(
            f"CREATE TABLE IF NOT EXISTS {partition_name} "
            f"PARTITION OF {table} "
            f"FOR VALUES FROM ('{start_str}') TO ('{end_str}');"
        )

    return statements


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect != "postgresql":
        # SQLite: just add indexes for performance, no partitioning
        op.execute("CREATE INDEX IF NOT EXISTS ix_anomalies_created_at ON anomalies(created_at);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_anomalies_pod_metric ON anomalies(pod, metric);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_anomalies_namespace ON anomalies(namespace);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_audit_created_at ON audit(created_at);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_audit_actor ON audit(actor);")
        op.execute("CREATE INDEX IF NOT EXISTS ix_audit_event_type ON audit(event_type);")
        return

    # ── PostgreSQL: Convert to partitioned tables ──────────────────

    # Step 1: Rename existing tables
    op.execute("ALTER TABLE IF EXISTS anomalies RENAME TO anomalies_old;")
    op.execute("ALTER TABLE IF EXISTS audit RENAME TO audit_old;")

    # Step 2: Create new partitioned anomalies table
    op.execute("""
    CREATE TABLE anomalies (
        id BIGSERIAL,
        timestamp BIGINT,
        pod TEXT,
        namespace TEXT,
        metric TEXT,
        value FLOAT,
        unit TEXT,
        z_score FLOAT,
        is_anomaly INTEGER,
        window_size INTEGER,
        source TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        PRIMARY KEY (id, created_at)
    ) PARTITION BY RANGE (created_at);
    """)

    # Step 3: Create new partitioned audit table
    op.execute("""
    CREATE TABLE audit (
        id BIGSERIAL,
        event_type TEXT NOT NULL,
        actor TEXT,
        target TEXT,
        payload TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        PRIMARY KEY (id, created_at)
    ) PARTITION BY RANGE (created_at);
    """)

    # Step 4: Create monthly partitions
    for stmt in _generate_monthly_partitions("anomalies", months_ahead=6):
        op.execute(stmt)

    for stmt in _generate_monthly_partitions("audit", months_ahead=6):
        op.execute(stmt)

    # Step 5: Create a default partition to catch anything outside range
    op.execute("CREATE TABLE IF NOT EXISTS anomalies_default PARTITION OF anomalies DEFAULT;")
    op.execute("CREATE TABLE IF NOT EXISTS audit_default PARTITION OF audit DEFAULT;")

    # Step 6: Migrate data from old tables
    op.execute("""
    INSERT INTO anomalies (id, timestamp, pod, namespace, metric, value, unit, z_score, is_anomaly, window_size, source, created_at)
    SELECT id, timestamp, pod, namespace, metric, value, unit, z_score, is_anomaly, window_size, source,
           COALESCE(created_at::timestamp, NOW())
    FROM anomalies_old;
    """)

    op.execute("""
    INSERT INTO audit (id, event_type, actor, target, payload, created_at)
    SELECT id, event_type, actor, target, payload,
           COALESCE(created_at::timestamp, NOW())
    FROM audit_old;
    """)

    # Step 7: Drop old tables
    op.execute("DROP TABLE IF EXISTS anomalies_old CASCADE;")
    op.execute("DROP TABLE IF EXISTS audit_old CASCADE;")

    # Step 8: Create indexes on partitioned tables
    op.execute("CREATE INDEX ix_anomalies_created_at ON anomalies (created_at);")
    op.execute("CREATE INDEX ix_anomalies_pod_metric ON anomalies (pod, metric);")
    op.execute("CREATE INDEX ix_anomalies_namespace_ts ON anomalies (namespace, created_at);")
    op.execute("CREATE INDEX ix_anomalies_is_anomaly ON anomalies (is_anomaly) WHERE is_anomaly = 1;")

    op.execute("CREATE INDEX ix_audit_created_at ON audit (created_at);")
    op.execute("CREATE INDEX ix_audit_actor ON audit (actor);")
    op.execute("CREATE INDEX ix_audit_event_type ON audit (event_type);")
    op.execute("CREATE INDEX ix_audit_target ON audit (target);")

    # Step 9: Reset sequences when the legacy sequence survived the table swap.
    # Some existing databases used integer IDs without a PostgreSQL sequence.
    op.execute("""
    DO $$
    BEGIN
        IF to_regclass('anomalies_id_seq') IS NOT NULL THEN
            PERFORM setval('anomalies_id_seq', COALESCE((SELECT MAX(id) FROM anomalies), 1));
        END IF;
        IF to_regclass('audit_id_seq') IS NOT NULL THEN
            PERFORM setval('audit_id_seq', COALESCE((SELECT MAX(id) FROM audit), 1));
        END IF;
    END;
    $$;
    """)

    # Step 10: Create auto-partition function (creates next month's partition automatically)
    op.execute("""
    CREATE OR REPLACE FUNCTION create_monthly_partition()
    RETURNS void LANGUAGE plpgsql AS $$
    DECLARE
        next_month_start DATE;
        next_month_end DATE;
        partition_name TEXT;
        tables TEXT[] := ARRAY['anomalies', 'audit'];
        t TEXT;
    BEGIN
        next_month_start := date_trunc('month', NOW() + interval '1 month')::date;
        next_month_end := (next_month_start + interval '1 month')::date;

        FOREACH t IN ARRAY tables LOOP
            partition_name := t || '_y' || EXTRACT(YEAR FROM next_month_start)::text
                              || 'm' || LPAD(EXTRACT(MONTH FROM next_month_start)::text, 2, '0');
            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = partition_name
            ) THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                    partition_name, t, next_month_start, next_month_end
                );
                RAISE NOTICE 'Created partition: %', partition_name;
            END IF;
        END LOOP;
    END;
    $$;
    """)

    # Step 11: Create a cron-friendly wrapper (call via pg_cron or external scheduler)
    op.execute("""
    COMMENT ON FUNCTION create_monthly_partition() IS
        'Call monthly to pre-create next month partition. Safe to call multiple times.';
    """)


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect != "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_anomalies_created_at;")
        op.execute("DROP INDEX IF EXISTS ix_anomalies_pod_metric;")
        op.execute("DROP INDEX IF EXISTS ix_anomalies_namespace;")
        op.execute("DROP INDEX IF EXISTS ix_audit_created_at;")
        op.execute("DROP INDEX IF EXISTS ix_audit_actor;")
        op.execute("DROP INDEX IF EXISTS ix_audit_event_type;")
        return

    # Convert back to regular tables (data preserved in default partition)
    op.execute("DROP FUNCTION IF EXISTS create_monthly_partition();")

    # Recreate as regular tables
    op.execute("""
    CREATE TABLE anomalies_new (
        id SERIAL PRIMARY KEY,
        timestamp BIGINT,
        pod TEXT,
        namespace TEXT,
        metric TEXT,
        value FLOAT,
        unit TEXT,
        z_score FLOAT,
        is_anomaly INTEGER,
        window_size INTEGER,
        source TEXT,
        created_at TEXT
    );
    """)
    op.execute("""
    INSERT INTO anomalies_new (id, timestamp, pod, namespace, metric, value, unit, z_score, is_anomaly, window_size, source, created_at)
    SELECT id, timestamp, pod, namespace, metric, value, unit, z_score, is_anomaly, window_size, source, created_at::text
    FROM anomalies;
    """)
    op.execute("DROP TABLE anomalies CASCADE;")
    op.execute("ALTER TABLE anomalies_new RENAME TO anomalies;")

    op.execute("""
    CREATE TABLE audit_new (
        id SERIAL PRIMARY KEY,
        event_type TEXT NOT NULL,
        actor TEXT,
        target TEXT,
        payload TEXT,
        created_at TEXT NOT NULL
    );
    """)
    op.execute("""
    INSERT INTO audit_new (id, event_type, actor, target, payload, created_at)
    SELECT id, event_type, actor, target, payload, created_at::text
    FROM audit;
    """)
    op.execute("DROP TABLE audit CASCADE;")
    op.execute("ALTER TABLE audit_new RENAME TO audit;")
