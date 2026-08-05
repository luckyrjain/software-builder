// Fixture: scan must FAIL — MySQL IF() SQL expression function (not the Java `if` keyword).
public class IfFunctionQuery {
    static final String SQL =
        "SELECT IF(status=1,'active','inactive') FROM tbl_accounts";
}
