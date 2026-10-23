#!/usr/bin/env python3
"""Synthetic demo: an agent report with good and bad citations.

All sources and claims are invented for the demo.
"""

import json
import os
import tempfile

import citation_check as cc

SOURCES = {
    "incident-report.txt": (
        "Postmortem: the cache fleet was drained at 03:12 UTC after the "
        "config push. Error rate peaked at 41 percent and recovered by "
        "03:47 UTC once the rollback completed."
    ),
    "metrics-note.txt": (
        "Weekly note: p99 latency held at 220 ms after the index change, "
        "down from 480 ms the week before."
    ),
}

CLAIMS = [
    {"id": "c1", "text": "The outage started at 03:12 UTC after a config push.",
     "citations": [{"source": "incident-report.txt",
                    "quote": "cache fleet was drained at 03:12 UTC after the config push"}]},
    {"id": "c2", "text": "p99 latency improved from 480 ms to 220 ms.",
     "citations": [{"source": "metrics-note.txt",
                    "quote": "p99 latency held at 220 ms after the index change"}]},
    {"id": "c3", "text": "The team followed the runbook exactly.",
     "citations": []},
    {"id": "c4", "text": "Error rate peaked at 90 percent.",
     "citations": [{"source": "incident-report.txt",
                    "quote": "error rate peaked at 90 percent during the incident"}]},
    {"id": "c5", "text": "Latency recovered after the rollback.",
     "citations": [{"source": "metrics-note.txt",
                    "quote": "recovered by 03:47 UTC once the rollback completed"}]},
    {"id": "c6", "text": "The CEO confirmed the timeline.",
     "citations": [{"source": "ceo-email.txt",
                    "quote": "I confirm the timeline is accurate"}]},
]


def main():
    d = tempfile.mkdtemp()
    corpus = os.path.join(d, "corpus")
    os.makedirs(corpus)
    for name, text in SOURCES.items():
        with open(os.path.join(corpus, name), "w") as f:
            f.write(text)
    claims_path = os.path.join(d, "claims.jsonl")
    with open(claims_path, "w") as f:
        for rec in CLAIMS:
            f.write(json.dumps(rec) + "\n")
    print("corpus:", ", ".join(sorted(SOURCES)))
    print("claims:", len(CLAIMS))
    print()
    findings = cc.run(claims_path, corpus)
    print(cc.format_text(findings) if findings else "no findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
