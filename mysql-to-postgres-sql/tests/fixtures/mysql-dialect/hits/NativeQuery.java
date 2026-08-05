// Fixture: scan must FAIL (TIMESTAMPDIFF)
public class NativeQuery {
    static final String SQL =
        "SELECT TIMESTAMPDIFF(MINUTE, tsc.added_timestamp, CURRENT_TIMESTAMP()) FROM tbl_sms";
}
