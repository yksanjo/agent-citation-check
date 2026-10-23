# agent-citation-check

Offline verifier for the citations in an agent-written report.

Agents write reports that cite sources. Sometimes a claim has no citation, the cited source does not exist, the quote was never said by that source, or the quote is real but attributed to the wrong document. This tool cross-checks a claim log against a local corpus of source texts and reports which citations actually hold up. It never touches the network, never calls a model, and cannot judge whether a claim is true - only whether its cited support is present, real, and correctly attributed.

## Claim log format

One JSON object per line:

```jsonl
{"id": "c1", "text": "The outage started at 03:12 UTC.", "citations": [{"source": "incident-report.txt", "quote": "drained at 03:12 UTC after the config push"}]}
```

- `id` and `text` are required strings.
- `citations` is a list of `{"source": ..., "quote": ...}` pairs. `source` names a file under the corpus directory; `quote` is a verbatim span from that file.

## What it reports

| Code | Severity | Signal |
| --- | --- | --- |
| `unverified-quote` | error | quoted span appears in no corpus source - possible fabricated citation |
| `missing-source` | error | cited source file is not in the corpus |
| `uncited-claim` | error | claim carries no citations at all |
| `misattributed-quote` | warning | quote is real but lives in a different source than the one cited |
| `empty-quote` | warning | quote under 12 chars - too generic to verify support |
| `bad-record` | error | malformed claim line or citation shape |
| `no-claims` / `no-corpus` | error | inputs missing or empty |

## Usage

```bash
python3 citation_check.py claims.jsonl --corpus ./sources
python3 citation_check.py claims.jsonl --corpus ./sources --min-severity error
python3 citation_check.py claims.jsonl --corpus ./sources --format json
python3 demo.py
python3 -m unittest test_citation_check
```

Exit code is 1 when any reported finding is an error, else 0, so it can gate a publishing step.

## How matching works

Case and whitespace are normalized before comparison, so re-wrapped text still matches. Punctuation and numbers are kept: a quote that changes "1,000" to "1000" does not match. Every citation must carry a verbatim quote - a bare source name is not checkable and gets no free pass.

## Honest limits

- It verifies attribution, not truth. A claim can be faithfully quoted from a source that is itself wrong.
- Substring matching cannot tell whether the quote actually supports the claim's meaning; a real quote can be cited for a claim it contradicts. That judgment needs a reader or a model - this tool is deliberately neither.
- Claims with no citations are flagged, but a citation requirement must come from whoever runs the check; the tool cannot force an agent to cite.
- Sources are local text files. It does not fetch URLs or verify that a cited URL's live content matches.
- Paraphrased citations fail by design: only verbatim spans verify. If your citation style paraphrases, this tool will report everything.
- Demo fixtures are synthetic and invented.

## License

MIT
