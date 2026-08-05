// Fixture: scan must FAIL — JSON_EXTRACT and MATCH...AGAINST fulltext search.
public class JsonFulltextQuery {
    static final String JSON_SQL =
        "SELECT JSON_EXTRACT(payload, '$.userId') FROM tbl_events";
    static final String FULLTEXT_SQL =
        "SELECT * FROM tbl_articles WHERE MATCH(title, body) AGAINST('refund policy')";
}
