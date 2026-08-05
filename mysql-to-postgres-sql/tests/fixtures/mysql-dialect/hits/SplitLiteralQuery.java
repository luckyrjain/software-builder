// Fixture: scan must FAIL — CAST(...AS CHAR) split across concatenated string literals,
// a pattern real-world domain packs commonly hit.
public class SplitLiteralQuery {
    static final String SQL =
        "SELECT CAST(balance "
            + "AS CHAR) FROM tbl_wallet";
}
