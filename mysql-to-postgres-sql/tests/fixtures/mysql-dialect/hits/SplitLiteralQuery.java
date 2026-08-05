// Fixture: scan must FAIL — CAST(...AS CHAR) split across concatenated string literals,
// the exact style shown in reference/domain-packs/collection-mpokket.md's own examples.
public class SplitLiteralQuery {
    static final String SQL =
        "SELECT CAST(balance "
            + "AS CHAR) FROM tbl_wallet";
}
