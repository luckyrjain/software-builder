-- Fixture: portable SQL an AST pass should NOT flag, including a comment that mentions a
-- MySQL-only function by name — proves comment-awareness the regex scan structurally lacks.
-- (Historically this table used SUBSTRING_INDEX() and UNIX_TIMESTAMP() before the Postgres migration.)
SELECT id, name FROM users WHERE created_at > '2020-01-01';

SELECT split_part(a, ',', 1) FROM t;

SELECT EXTRACT(DAY FROM (a - b)) FROM t;

INSERT INTO t (a, b) VALUES (1, 2)
ON CONFLICT (a) DO UPDATE SET b = EXCLUDED.b;
