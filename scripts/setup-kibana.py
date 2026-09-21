"""Create/update a deterministic Kibana data view after Kibana becomes healthy."""

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = os.getenv("KIBANA_URL", "http://kibana:5601")


def api(path, body=None, method="POST"):
    request = Request(
        BASE + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "kbn-xsrf": "campus-setup"},
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def main():
    view = {"title": "campus-logs-*", "timeFieldName": "@timestamp", "name": "Campus request logs"}
    try:
        api("/api/data_views/data_view/campus-logs", method="GET")
    except HTTPError as exc:
        if exc.code != 404:
            raise
        api("/api/data_views/data_view", {"data_view": {"id": "campus-logs", **view}})
    else:
        api("/api/data_views/data_view/campus-logs", {"data_view": view})
    api("/api/data_views/default", {"data_view_id": "campus-logs", "force": True})
    print("Kibana data view campus-logs is ready. Open Discover, choose last 15 minutes.")


if __name__ == "__main__":
    main()
