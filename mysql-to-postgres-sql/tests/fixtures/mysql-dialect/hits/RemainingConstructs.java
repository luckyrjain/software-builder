// Fixture: scan must FAIL — one line per otherwise-untested dialect construct in the scan
// PATTERN, so a future regex edit that silently drops one of these fails the pressure harness.
public class RemainingConstructs {
    static final String GROUP_CONCAT_SQL =
        "SELECT GROUP_CONCAT(name SEPARATOR ',') FROM tbl_tags";
    static final String ON_DUPLICATE_SQL =
        "INSERT INTO tbl_counter (id, n) VALUES (1, 1) ON DUPLICATE KEY UPDATE n = n + 1";
    static final String INSERT_IGNORE_SQL =
        "INSERT IGNORE INTO tbl_events (id, payload) VALUES (?, ?)";
    static final String FIND_IN_SET_SQL =
        "SELECT * FROM tbl_products WHERE FIND_IN_SET('electronics', categories)";
    static final String INSTR_SQL =
        "SELECT INSTR(email, '@') FROM tbl_users";
    static final String REGEXP_SQL =
        "SELECT * FROM tbl_users WHERE email REGEXP '^[a-z]+@'";
    static final String RLIKE_SQL =
        "SELECT * FROM tbl_users WHERE email RLIKE '^[a-z]+@'";
    static final String ISNULL_SQL =
        "SELECT * FROM tbl_orders WHERE ISNULL(shipped_at)";
    static final String ADDTIME_SQL =
        "SELECT ADDTIME(created_at, '0 05:30:00') FROM tbl_sessions";
    static final String SUBSTRING_INDEX_SQL =
        "SELECT SUBSTRING_INDEX(email, '@', 1) FROM tbl_users";
    static final String CONVERT_TZ_SQL =
        "SELECT CONVERT_TZ(created_at, 'UTC', 'America/New_York') FROM tbl_events";
    static final String JSON_UNQUOTE_SQL =
        "SELECT JSON_UNQUOTE(JSON_EXTRACT(payload, '$.userId')) FROM tbl_events";
    static final String JSON_ARRAYAGG_SQL =
        "SELECT JSON_ARRAYAGG(id) FROM tbl_items";
    static final String JSON_OBJECTAGG_SQL =
        "SELECT JSON_OBJECTAGG(k, v) FROM tbl_kv";
    static final String JSON_CONTAINS_SQL =
        "SELECT * FROM tbl_docs WHERE JSON_CONTAINS(tags, '\"urgent\"')";
    static final String JSON_SET_SQL =
        "UPDATE tbl_docs SET payload = JSON_SET(payload, '$.seen', true)";
    static final String JSON_REMOVE_SQL =
        "UPDATE tbl_docs SET payload = JSON_REMOVE(payload, '$.draft')";
    static final String JSON_MERGE_SQL =
        "UPDATE tbl_docs SET payload = JSON_MERGE(payload, '{\"seen\":true}')";
    static final String YEAR_SQL =
        "SELECT * FROM tbl_orders WHERE YEAR(created_at) = 2024";
    static final String MONTH_SQL =
        "SELECT * FROM tbl_orders WHERE MONTH(created_at) = 6";
    static final String WEEK_SQL =
        "SELECT * FROM tbl_orders WHERE WEEK(created_at) = 24";
}
