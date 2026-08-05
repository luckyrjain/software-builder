// Fixture: scan must PASS
public class PortableQuery {
    static final String SQL =
        "SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - tsc.added_timestamp)) / 60 FROM tbl_sms";

    // Lambdas/method refs must not false-positive as MySQL JSON `->`/`->>` operators.
    java.util.function.Function<Integer, Integer> increment = x -> x + 1;

    // Bare `col->'key'` (no JSON_ prefix) is valid PG jsonb syntax too — not scanned.
    static final String JSONB_SQL = "SELECT payload->'userId' FROM tbl_events";

    // Ordinary LIMIT_/DIV identifiers must not false-positive as MySQL LIMIT/DIV constructs.
    private static final int LIMIT_KEY = computeThreshold(baseValue, 5);
    private static final int RATE_LIMIT_THRESHOLD = computeThreshold(baseValue, 42);
    // DIV as a standalone word (not a SQL operator) followed by digits/quotes nearby.
    // Splitting work across DIV nodes: worker '0' handles even, worker 1 handles odd.
}
