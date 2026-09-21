"""Idempotent, bounded local Elasticsearch setup; no dependencies beyond stdlib."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
ROOT = Path(__file__).resolve().parents[1] / "observability" / "elasticsearch"


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = Request(
        BASE + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def main():
    api("PUT", "/_ilm/policy/campus-logs-7d", json.loads((ROOT / "ilm-policy.json").read_text()))
    api(
        "PUT",
        "/_index_template/campus-logs",
        json.loads((ROOT / "index-template.json").read_text()),
    )
    try:
        api("GET", "/_alias/campus-logs")
    except HTTPError as exc:
        if exc.code != 404:
            raise
        api("PUT", "/campus-logs-000001", {"aliases": {"campus-logs": {"is_write_index": True}}})
    print(
        json.dumps(
            {
                "policy": api("GET", "/_ilm/policy/campus-logs-7d"),
                "indices": api("GET", "/campus-logs-*/_ilm/explain"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
