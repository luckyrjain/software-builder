// Fixture: scan must FAIL — lowercase MySQL SQL (common with ORMs/style guides) must not be
// invisible to the scan just because the tokens aren't uppercase. Only tokens in the
// case-insensitive group (PATTERN_CI) belong here — do not add lowercase IF(/YEAR(/MONTH(/WEEK(/
// DIV/LIMIT here, those must stay case-sensitive-uppercase-only (see PortableQuery.java).
public class LowercaseQuery {
    static final String SQL =
        "select timestampdiff(minute, tsc.added_timestamp, current_timestamp()) from tbl_sms";

    static final String SQL2 =
        "select date_format(created_at, '%Y-%m-%d') from tbl_orders";
}
