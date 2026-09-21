from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from experiments.cardinality import create_demo


def test_100_labels_then_one_after_restart():
    for high, expected in [(True, 100), (False, 1)]:
        with TestClient(create_demo(high)) as client:
            for _ in range(100):
                assert client.post("/hit").status_code == 200
            assert client.post("/hit").status_code == 429
            families = text_string_to_metric_families(client.get("/metrics").text)
            samples = [
                sample
                for family in families
                for sample in family.samples
                if sample.name == "demo_requests_total"
            ]
            assert len(samples) == expected
            assert sum(sample.value for sample in samples) == 100
