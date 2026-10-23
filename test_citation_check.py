import json
import os
import shutil
import tempfile
import unittest

import citation_check as cc


class CitationTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.corpus = os.path.join(self.dir, "corpus")
        os.makedirs(self.corpus)
        self.claims_path = os.path.join(self.dir, "claims.jsonl")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write_source(self, name, text):
        with open(os.path.join(self.corpus, name), "w") as f:
            f.write(text)

    def write_claims(self, records):
        with open(self.claims_path, "w") as f:
            for r in records:
                if isinstance(r, str):
                    f.write(r + "\n")
                else:
                    f.write(json.dumps(r) + "\n")

    def codes(self, findings):
        return {f["code"] for f in findings}

    def test_verified_claim_produces_no_findings(self):
        self.write_source("notes.txt", "The deploy finished at 14:30 with zero errors.")
        self.write_claims([{"id": "c1", "text": "Deploy was clean.",
                            "citations": [{"source": "notes.txt",
                                           "quote": "finished at 14:30 with zero errors"}]}])
        self.assertEqual(cc.run(self.claims_path, self.corpus), [])

    def test_uncited_claim_is_error(self):
        self.write_source("notes.txt", "anything")
        self.write_claims([{"id": "c1", "text": "unsupported claim", "citations": []}])
        findings = cc.run(self.claims_path, self.corpus)
        self.assertIn("uncited-claim", self.codes(findings))
        self.assertEqual(findings[0]["severity"], "error")

    def test_missing_citations_field_is_error(self):
        self.write_source("notes.txt", "anything")
        self.write_claims([{"id": "c1", "text": "no citations key at all"}])
        self.assertIn("uncited-claim", self.codes(cc.run(self.claims_path, self.corpus)))

    def test_missing_source_is_error(self):
        self.write_source("notes.txt", "real content here")
        self.write_claims([{"id": "c1", "text": "claim",
                            "citations": [{"source": "ghost.txt",
                                           "quote": "some long enough quote"}]}])
        self.assertIn("missing-source", self.codes(cc.run(self.claims_path, self.corpus)))

    def test_unverified_quote_is_error(self):
        self.write_source("notes.txt", "The deploy finished at 14:30.")
        self.write_claims([{"id": "c1", "text": "claim",
                            "citations": [{"source": "notes.txt",
                                           "quote": "the deploy never happened at all"}]}])
        findings = cc.run(self.claims_path, self.corpus)
        self.assertIn("unverified-quote", self.codes(findings))
        err = [f for f in findings if f["code"] == "unverified-quote"][0]
        self.assertEqual(err["severity"], "error")

    def test_misattributed_quote_is_warning(self):
        self.write_source("a.txt", "Alpha document about rivers and deltas.")
        self.write_source("b.txt", "Beta document about rivers and deltas.")
        quote = "document about rivers and deltas"
        self.write_claims([{"id": "c1", "text": "claim",
                            "citations": [{"source": "a.txt", "quote": quote}]}])
        # quote is in a.txt: verified, no finding
        self.assertEqual(cc.run(self.claims_path, self.corpus), [])
        # now cite the wrong file with a quote unique to b.txt
        self.write_source("b.txt", "Beta document has a unique phrase about estuaries.")
        self.write_claims([{"id": "c2", "text": "claim",
                            "citations": [{"source": "a.txt",
                                           "quote": "unique phrase about estuaries"}]}])
        findings = cc.run(self.claims_path, self.corpus)
        self.assertIn("misattributed-quote", self.codes(findings))
        warn = [f for f in findings if f["code"] == "misattributed-quote"][0]
        self.assertEqual(warn["severity"], "warning")

    def test_short_quote_is_warning(self):
        self.write_source("notes.txt", "The sky is blue today.")
        self.write_claims([{"id": "c1", "text": "claim",
                            "citations": [{"source": "notes.txt", "quote": "sky"}]}])
        self.assertIn("empty-quote", self.codes(cc.run(self.claims_path, self.corpus)))

    def test_bad_record_line(self):
        self.write_source("notes.txt", "x")
        self.write_claims(["{not valid json"])
        self.assertIn("bad-record", self.codes(cc.run(self.claims_path, self.corpus)))

    def test_record_missing_fields(self):
        self.write_source("notes.txt", "x")
        self.write_claims([{"text": "no id"}])
        self.assertIn("bad-record", self.codes(cc.run(self.claims_path, self.corpus)))

    def test_normalization_matches_across_case_and_whitespace(self):
        self.write_source("notes.txt", "Deploy   FINISHED\nat 14:30   with zero errors.")
        self.write_claims([{"id": "c1", "text": "claim",
                            "citations": [{"source": "notes.txt",
                                           "quote": "deploy finished at 14:30 with zero errors"}]}])
        self.assertEqual(cc.run(self.claims_path, self.corpus), [])

    def test_punctuation_difference_does_not_match(self):
        self.write_source("notes.txt", "Revenue was 1,000 dollars last quarter.")
        self.write_claims([{"id": "c1", "text": "claim",
                            "citations": [{"source": "notes.txt",
                                           "quote": "revenue was 1000 dollars last quarter"}]}])
        self.assertIn("unverified-quote", self.codes(cc.run(self.claims_path, self.corpus)))

    def test_missing_claims_file(self):
        self.write_source("notes.txt", "x")
        findings = cc.run(os.path.join(self.dir, "nope.jsonl"), self.corpus)
        self.assertIn("no-claims", self.codes(findings))

    def test_missing_corpus_dir(self):
        self.write_claims([{"id": "c1", "text": "t", "citations": []}])
        findings = cc.run(self.claims_path, os.path.join(self.dir, "no-such-dir"))
        self.assertIn("no-corpus", self.codes(findings))

    def test_empty_corpus_dir(self):
        self.write_claims([{"id": "c1", "text": "t", "citations": []}])
        findings = cc.run(self.claims_path, self.corpus)
        self.assertIn("no-corpus", self.codes(findings))

    def test_nested_corpus_files(self):
        os.makedirs(os.path.join(self.corpus, "sub"))
        self.write_source(os.path.join("sub", "deep.txt"), "deep source with enough content")
        self.write_claims([{"id": "c1", "text": "claim",
                            "citations": [{"source": os.path.join("sub", "deep.txt"),
                                           "quote": "deep source with enough content"}]}])
        self.assertEqual(cc.run(self.claims_path, self.corpus), [])

    def test_multiple_citations_all_checked(self):
        self.write_source("a.txt", "first supporting fact is here in full")
        self.write_source("b.txt", "second supporting fact is here in full")
        self.write_claims([{"id": "c1", "text": "claim",
                            "citations": [
                                {"source": "a.txt", "quote": "first supporting fact is here"},
                                {"source": "b.txt", "quote": "fabricated second support"},
                            ]}])
        findings = cc.run(self.claims_path, self.corpus)
        self.assertEqual(self.codes(findings), {"unverified-quote"})

    def test_min_severity_filter(self):
        findings = [
            {"code": "a", "severity": "warning", "claim": "c", "detail": "d"},
            {"code": "b", "severity": "error", "claim": "c", "detail": "d"},
        ]
        self.assertEqual(len(cc.filter_severity(findings, "warning")), 2)
        self.assertEqual(len(cc.filter_severity(findings, "error")), 1)

    def test_cli_exit_codes(self):
        self.write_source("notes.txt", "The deploy finished at 14:30 with zero errors.")
        self.write_claims([{"id": "c1", "text": "ok",
                            "citations": [{"source": "notes.txt",
                                           "quote": "finished at 14:30 with zero errors"}]}])
        self.assertEqual(cc.main([self.claims_path, "--corpus", self.corpus]), 0)
        self.write_claims([{"id": "c2", "text": "bad", "citations": []}])
        self.assertEqual(cc.main([self.claims_path, "--corpus", self.corpus]), 1)

    def test_cli_json_format(self):
        import io
        from contextlib import redirect_stdout
        self.write_source("notes.txt", "x")
        self.write_claims([{"id": "c1", "text": "bad", "citations": []}])
        buf = io.StringIO()
        with redirect_stdout(buf):
            cc.main([self.claims_path, "--corpus", self.corpus, "--format", "json"])
        parsed = json.loads(buf.getvalue())
        self.assertEqual(parsed[0]["code"], "uncited-claim")


if __name__ == "__main__":
    unittest.main()
