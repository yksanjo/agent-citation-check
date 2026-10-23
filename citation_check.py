#!/usr/bin/env python3
"""Offline claim-citation verifier for agent-written reports.

Agents write reports that cite sources. Sometimes the citation is missing,
points at a source that does not exist, or quotes text the source never said.
This tool cross-checks a claim log against a local corpus of source texts and
reports which claims are actually grounded. It never touches the network,
never calls a model, and cannot judge whether a claim is true - only whether
its cited support is present, real, and correctly attributed.
"""

import argparse
import json
import os
import re
import sys

SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}
MIN_QUOTE_LEN = 12  # shorter spans are too generic to verify support


def normalize(text):
    """Casefold and collapse whitespace so formatting differences don't
    produce false mismatches. Punctuation is kept: a quote that changes
    words or numbers must not match."""
    return re.sub(r"\s+", " ", str(text)).strip().casefold()


def finding(code, severity, claim_id, detail):
    return {"code": code, "severity": severity, "claim": claim_id, "detail": detail}


def load_claims(path):
    """One JSON object per line: {"id": str, "text": str, "citations": [...]}.
    Returns (claims, findings)."""
    claims = []
    findings = []
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                findings.append(finding("bad-record", "error", "line-%d" % lineno,
                                        "malformed JSON: %s" % e))
                continue
            if not isinstance(rec, dict) or not rec.get("id") or not isinstance(rec.get("text"), str):
                findings.append(finding("bad-record", "error", "line-%d" % lineno,
                                        "record needs string 'id' and 'text' fields"))
                continue
            claims.append(rec)
    return claims, findings


def load_corpus(corpus_dir):
    """Every regular file under corpus_dir is a named source."""
    corpus = {}
    for root, _dirs, files in os.walk(corpus_dir):
        for name in sorted(files):
            p = os.path.join(root, name)
            rel = os.path.relpath(p, corpus_dir)
            try:
                with open(p, errors="replace") as f:
                    corpus[rel] = f.read()
            except OSError:
                pass
    return corpus


def check_claims(claims, corpus):
    findings = []
    norm_corpus = {name: normalize(text) for name, text in corpus.items()}
    for rec in claims:
        cid = str(rec["id"])
        citations = rec.get("citations")
        if not citations:
            findings.append(finding(
                "uncited-claim", "error", cid,
                "claim has no citations: %s" % rec["text"][:80]))
            continue
        if not isinstance(citations, list):
            findings.append(finding("bad-record", "error", cid,
                                    "'citations' must be a list"))
            continue
        for cit in citations:
            if not isinstance(cit, dict) or not cit.get("source"):
                findings.append(finding("bad-record", "error", cid,
                                        "citation needs a 'source' field"))
                continue
            src = str(cit["source"])
            quote = str(cit.get("quote", ""))
            if src not in norm_corpus:
                findings.append(finding(
                    "missing-source", "error", cid,
                    "cited source '%s' is not in the corpus" % src))
                continue
            if len(normalize(quote)) < MIN_QUOTE_LEN:
                findings.append(finding(
                    "empty-quote", "warning", cid,
                    "quote under %d chars in '%s' is too generic to verify support"
                    % (MIN_QUOTE_LEN, src)))
                continue
            nq = normalize(quote)
            if nq in norm_corpus[src]:
                continue  # verified
            # Not in the cited source. Does it appear in a different one?
            elsewhere = [name for name, text in norm_corpus.items()
                         if name != src and nq in text]
            if elsewhere:
                findings.append(finding(
                    "misattributed-quote", "warning", cid,
                    "quote not found in '%s' but appears in %s - citation points "
                    "at the wrong source" % (src, ", ".join(sorted(elsewhere)))))
            else:
                findings.append(finding(
                    "unverified-quote", "error", cid,
                    "quote not found in '%s' or any other corpus source - "
                    "possible fabricated citation" % src))
    return findings


def run(claims_path, corpus_dir):
    if not os.path.isdir(corpus_dir):
        return [finding("no-corpus", "error", "(input)",
                        "corpus directory not found: %s" % corpus_dir)]
    try:
        claims, findings = load_claims(claims_path)
    except FileNotFoundError:
        return [finding("no-claims", "error", "(input)",
                        "claims file not found: %s" % claims_path)]
    corpus = load_corpus(corpus_dir)
    if not corpus:
        findings.append(finding("no-corpus", "error", "(input)",
                                "corpus directory has no readable files: %s" % corpus_dir))
        return findings
    findings.extend(check_claims(claims, corpus))
    return findings


def filter_severity(findings, min_severity):
    floor = SEVERITY_ORDER[min_severity]
    return [f for f in findings if SEVERITY_ORDER[f["severity"]] >= floor]


def format_text(findings):
    return "\n".join("%-7s %-19s %-12s %s" % (
        f["severity"].upper(), f["code"], f["claim"], f["detail"])
        for f in findings)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify that an agent report's citations are real and correctly attributed.")
    parser.add_argument("claims", help="JSONL claim log")
    parser.add_argument("--corpus", required=True,
                        help="directory of source text files the claims cite")
    parser.add_argument("--min-severity", choices=["info", "warning", "error"], default="info")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    findings = filter_severity(run(args.claims, args.corpus), args.min_severity)
    if args.format == "json":
        print(json.dumps(findings, indent=2))
    elif findings:
        print(format_text(findings))
    else:
        print("no findings")
    return 1 if any(f["severity"] == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
