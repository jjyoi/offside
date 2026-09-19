from app.pipeline.diff_parser import parse_diff

SAMPLE_DIFF = """diff --git a/checkout/client.ts b/checkout/client.ts
index d7d2320..3e5f4ab 100644
--- a/checkout/client.ts
+++ b/checkout/client.ts
@@ -1,3 +1,7 @@
 export async function fetchWithTimeout(url: string) {
-  return await fetch(url, { signal: AbortSignal.timeout(5000) });
+  return await fetch(url);
+}
+
+export function runQuery(userInput: string) {
+  return eval(userInput);
 }
"""


def test_parse_diff_extracts_file_and_hunk():
    hunks = parse_diff(SAMPLE_DIFF)
    assert len(hunks) == 1
    hunk = hunks[0]
    assert hunk.file == "checkout/client.ts"
    assert hunk.removed_lines == ["  return await fetch(url, { signal: AbortSignal.timeout(5000) });"]
    added_texts = [text for _, text in hunk.added_lines]
    assert "  return await fetch(url);" in added_texts
    assert "  return eval(userInput);" in added_texts


def test_parse_diff_line_numbers_start_at_hunk_header():
    hunks = parse_diff(SAMPLE_DIFF)
    first_added_line_no = hunks[0].added_lines[0][0]
    assert first_added_line_no == 2  # hunk starts at new-file line 1, first added line is the 2nd


def test_parse_diff_multiple_files():
    diff = SAMPLE_DIFF + (
        "diff --git a/other.ts b/other.ts\n"
        "index 1111111..2222222 100644\n"
        "--- a/other.ts\n"
        "+++ b/other.ts\n"
        "@@ -1,1 +1,1 @@\n"
        "-const a = 1;\n"
        "+const a = 2;\n"
    )
    hunks = parse_diff(diff)
    assert len(hunks) == 2
    assert hunks[1].file == "other.ts"


def test_parse_diff_empty_input():
    assert parse_diff("") == []
