import json
import sys
import time
from datetime import UTC, datetime
from urllib.parse import urlencode
from urllib.request import urlopen


def main():
    high = sys.argv[1] == "true"
    expected = 100 if high else 1
    query = urlencode({"query": 'count(demo_requests_total{job="cardinality-demo"})'})
    for _ in range(30):
        time.sleep(2)
        with urlopen("http://prometheus:9090/api/v1/query?" + query, timeout=5) as response:
            result = json.load(response)["data"]["result"]
        if result and int(result[0]["value"][1]) == expected:
            print(
                json.dumps(
                    {
                        "high_cardinality": high,
                        "accepted": 100,
                        "series": expected,
                        "utc": datetime.now(UTC).isoformat(),
                    }
                )
            )
            return
    raise SystemExit(f"Current series count did not become {expected} after scrapes")


if __name__ == "__main__":
    main()
