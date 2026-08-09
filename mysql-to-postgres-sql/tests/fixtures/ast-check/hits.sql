-- Fixture: MySQL-only constructs an AST pass should detect.
SELECT TIMESTAMPDIFF(DAY, a, b) FROM t;

SELECT SUBSTRING_INDEX(a, ',', 1) FROM t;

INSERT INTO t (a, b) VALUES (1, 2) ON DUPLICATE KEY UPDATE b = VALUES(b);

SELECT UNIX_TIMESTAMP(created_at) FROM events;

SELECT JSON_EXTRACT(data, '$.name') FROM t;
