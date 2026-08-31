-- Short-lived, one-time browser bootstrap codes for the private FRIDA operator
-- surface.  The bearer secret never reaches the browser or this table.
CREATE TABLE IF NOT EXISTS operator_access_links (
    code_digest TEXT PRIMARY KEY,
    expires_at TEXT NOT NULL,
    consumed_at TEXT
);
