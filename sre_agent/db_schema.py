"""Table schemas that work for both SQLite and PostgreSQL.

Import this module and pass the schema strings to ``Database.executescript()``
which handles DDL translation automatically.
"""

INCIDENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    query TEXT NOT NULL,
    query_keywords TEXT NOT NULL,
    tool_sequence TEXT NOT NULL,
    resolution TEXT NOT NULL,
    outcome TEXT DEFAULT 'unknown',
    namespace TEXT DEFAULT '',
    resource_type TEXT DEFAULT '',
    error_type TEXT DEFAULT '',
    tool_count INTEGER DEFAULT 0,
    rejected_tools INTEGER DEFAULT 0,
    duration_seconds REAL DEFAULT 0,
    score REAL DEFAULT 0
);
"""

RUNBOOKS_SCHEMA = """
CREATE TABLE IF NOT EXISTS runbooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    trigger_keywords TEXT NOT NULL,
    tool_sequence TEXT NOT NULL,
    success_count INTEGER DEFAULT 1,
    failure_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source_incident_id INTEGER
);
"""

PATTERNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,
    description TEXT NOT NULL,
    keywords TEXT NOT NULL,
    incident_ids TEXT NOT NULL,
    frequency INTEGER DEFAULT 1,
    last_seen TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'
);
"""

METRICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value REAL NOT NULL,
    window TEXT DEFAULT 'session'
);
"""

ACTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    finding_id TEXT,
    timestamp BIGINT,
    action_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    description TEXT DEFAULT '',
    result TEXT DEFAULT ''
);
"""

FINDINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    cluster TEXT NOT NULL,
    namespace TEXT DEFAULT '',
    resource TEXT DEFAULT '',
    severity TEXT DEFAULT 'info',
    message TEXT NOT NULL,
    timestamp BIGINT,
    resolved INTEGER DEFAULT 0
);
"""

INDEX_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_incidents_keywords ON incidents(query_keywords);
CREATE INDEX IF NOT EXISTS idx_incidents_error_type ON incidents(error_type);
CREATE INDEX IF NOT EXISTS idx_runbooks_keywords ON runbooks(trigger_keywords);
CREATE INDEX IF NOT EXISTS idx_patterns_keywords ON patterns(keywords);
CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
CREATE INDEX IF NOT EXISTS idx_findings_cluster ON findings(cluster);
"""

ALL_SCHEMAS = (
    INCIDENTS_SCHEMA
    + RUNBOOKS_SCHEMA
    + PATTERNS_SCHEMA
    + METRICS_SCHEMA
    + ACTIONS_SCHEMA
    + FINDINGS_SCHEMA
    + INDEX_SCHEMA
)
