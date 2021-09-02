"""Test /v1/datasets endpoints"""


import json

import boto3
from moto import mock_s3

from dashboard_api.core.config import BUCKET

DATASET_METADATA_FILENAME = "dev-dataset-metadata.json"


@mock_s3
def _setup_s3(empty=False):
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(BUCKET)
    bucket.create()
    if empty:
        return bucket
    datasets_domains = {
        "_all": {"co2": {"domain": ["2019-01-01T00:00:00Z", "2020-01-01T00:00:00Z"]}},
        "global": {"co2": {"domain": ["2019-01-01T00:00:00Z", "2020-01-01T00:00:00Z"]}},
        "tk": {},
        "ny": {},
    }
    for site_key in datasets_domains.keys():
        for dataset_id, domain_data in datasets_domains[site_key].items():
            datasets_domains[site_key][dataset_id] = {
                "id": dataset_id,
                "name": "test name",
                "type": "test type",
                "source": {"tiles": ["data.tif"], "type": "test type"},
                "domain": domain_data.get("domain"),
            }
    dataset_metadata_json = json.dumps(datasets_domains)
    s3_keys = [
        ("indicators/test/super.csv", b"test"),
        (DATASET_METADATA_FILENAME, dataset_metadata_json,),
    ]
    for key, content in s3_keys:
        bucket.put_object(Body=content, Key=key)
    return bucket


@mock_s3
def test_datasets(app):
    _setup_s3()
    response = app.get("v1/datasets")

    assert response.status_code == 200
    content = json.loads(response.content)

    assert "co2" in [d["id"] for d in content["datasets"]]


@mock_s3
def test_spotlight_datasets(app):
    _setup_s3()
    response = app.get("v1/datasets/tk")

    assert response.status_code == 200


@mock_s3
def test_incorrect_dataset_id(app):
    _setup_s3()

    response = app.get("/v1/datasets/NOT_A_VALID_DATASET")
    assert response.status_code == 404
