""" Dataset metadata generator lambda. """
import datetime
import json
import os
import re
import requests
from typing import Any, Dict, List, Optional, Union
import yaml

import boto3

BASE_PATH = os.path.abspath('.')
config = yaml.load(open(f"{BASE_PATH}/stack/config.yml", 'r'), Loader=yaml.FullLoader)

DATASETS_JSON_FILEPATH = os.path.join(BASE_PATH, "dashboard_api/db/static/datasets")
SITES_JSON_FILEPATH = os.path.join(BASE_PATH, "dashboard_api/db/static/sites")

DATASET_METADATA_FILENAME = os.environ.get("DATASET_METADATA_FILENAME", config.get('DATASET_METADATA_FILENAME'))
STAC_API_URL = config['STAC_API_URL']

s3 = boto3.resource("s3")
bucket = s3.Bucket(os.environ.get("DATA_BUCKET_NAME", config.get('BUCKET')))

DT_FORMAT = "%Y-%m-%d"
MT_FORMAT = "%Y%m"

# Can test this with python -m lambda.dataset_metadata_generator.src.main | jq .
# From the root directory of this project.
def handler(event, context):
    """
    Params:
    -------
    event (dict):
    content (dict):

    Both params are standard lambda handler invocation params but not used within this
    lambda's code.

    Returns:
    -------
    (string): JSON-encoded dict with top level keys for each of the possible
        queries that can be run against the `/datasets` endpoint (key: _all_ contains
        result of the LIST operation, each of other keys contain the result of
        GET /datasets/{spotlight_id | "global"})
    """

    # TODO: defined TypedDicts for these!
    listed_datasets = config['DATASETS']['STATIC']
    datasets = _gather_json_data(DATASETS_JSON_FILEPATH, filter=listed_datasets)
    if STAC_API_URL:
        stac_datasets = _fetch_stac_items()
        datasets.extend(stac_datasets)
    sites = _gather_json_data(SITES_JSON_FILEPATH)

    result = _gather_datasets_metadata(datasets, sites)
    # TODO: Protect from running _not_ in "production" deployment
    bucket.put_object(
        Body=json.dumps(result), Key=DATASET_METADATA_FILENAME, ContentType="application/json",
    )
    return result

def _fetch_stac_items():
    """ Fetches collections from a STAC catalogue and generates a metadata object for each collection. """
    stac_response = requests.get(f"{STAC_API_URL}/collections")
    if stac_response.status_code == 200:
        stac_collections = json.loads(stac_response.content).get('collections')
    stac_datasets = []
    for collection in stac_collections:
        # TODO: defined TypedDicts for these!
        stac_dataset = {
            "id": collection['id'],
            "name": collection['title'],
            "type": "raster",
            "time_unit": "day",
            "is_periodic": False,
            "source": {
                "type": "raster",
                # For now, don't list any tiles. We will want to mosaic STAC search results.
                "tiles": []
            },
            "info": collection['description'],
        }
        stac_datasets.append(stac_dataset)

    return stac_datasets

def _gather_datasets_metadata(datasets: List[dict], sites: List[dict]):
    """Reads through the s3 bucket to generate a file that contains
    the datasets for each given spotlight option (_all, global, tk, ny, sf,
    la, be, du, gh) and their respective domain for each spotlight

    Params:
    -------
    datasets (List[dict]): list of dataset metadata objects (contains fields
        like: s3_location, time_unit, swatch, exclusive_with, etc), to use
        to generate the result of each of the possible `/datasets` endpoint
        queries.
    sites (List[dict]): list of site metadata objects

    Returns:
    --------
    (dict): python object with result of each possible query against the `/datasets`
    endpoint with each dataset's associated domain.
    """

    metadata: Dict[str, dict] = {}

    for dataset in datasets:
        if dataset.get("s3_location"):
            domain_args = {
                "dataset_folder": dataset["s3_location"],
                "is_periodic": dataset.get("is_periodic"),
                "time_unit": dataset.get("time_unit"),
                "dataset_bucket": dataset.get("s3_bucket"),
            }
            domain = _get_dataset_domain(**domain_args)
            dataset['domain'] = domain
        
        metadata.setdefault("_all", {}).update({dataset["id"]: dataset})

        if _is_global_dataset(dataset):

            metadata.setdefault("global", {}).update(
                {dataset["id"]: dataset}
            )
            continue

        for site in sites:

            domain_args["spotlight_id"] = site["id"]

            if site["id"] in ["du", "gh"]:
                domain_args["spotlight_id"] = ["du", "gh", "EUPorts"]

            # skip adding dataset to metadata object if no dates were found for the given
            # spotlight (indicates dataset is not valid for that spotlight)
            try:
                domain = _get_dataset_domain(**domain_args)
            except NoKeysFoundForSpotlight:
                continue

            metadata.setdefault(site["id"], {}).update(
                {dataset["id"]: {"domain": domain}}
            )
    return metadata


def _gather_json_data(dirpath: str, filter: List[str] = None) -> List[dict]:
    """Gathers all JSON files from within a diven directory"""

    results = []
    for filename in os.listdir(dirpath):
        if not filename.endswith(".json"):
            continue
        if filter and not filename in filter:
            continue
        with open(os.path.join(dirpath, filename)) as f:
            results.append(json.load(f))
    return results


def _is_global_dataset(dataset: dict) -> bool:
    """Returns whether the given dataset is spotlight specific (FALSE)
    or non-spotlight specific (TRUE)"""
    return not any(
        [
            i in dataset["source"]["tiles"][0]
            for i in ["{spotlightId}", "greatlakes", "togo"]
            if dataset['source']['tiles']
        ]
    )


def _gather_s3_keys(
    spotlight_id: Optional[Union[str, List]] = None,
    prefix: Optional[str] = "",
    dataset_bucket: Optional[str] = None
) -> List[str]:
    """
    Returns a set of S3 keys. If no args are provided, the keys will represent
    the entire S3 bucket.
    Params:
    -------
    spotlight_id (Optional[str]):
        Id of a spotlight to filter keys by
    prefix (Optional[str]):
        S3 Prefix under which to gather keys, used to specifcy a specific
        dataset folder to search within.

    Returns:
    -------
    set(str)

    """
    s3_dataset_bucket = bucket if dataset_bucket == None else s3.Bucket(dataset_bucket)

    keys = [x.key for x in s3_dataset_bucket.objects.filter(Prefix=prefix)]

    if not spotlight_id:
        return keys

    if isinstance(spotlight_id, list):
        spotlight_id = "|".join([s for s in spotlight_id])

    pattern = re.compile(rf"""[^a-zA-Z0-9]({spotlight_id})[^a-zA-Z0-9]""")
    return list({key for key in keys if pattern.search(key, re.IGNORECASE,)})


def _get_dataset_domain(
    dataset_folder: str,
    is_periodic: bool,
    dataset_bucket: Optional[str] = None,
    spotlight_id: Optional[Union[str, List]] = None,
    time_unit: Optional[str] = "day",
):
    """
    Returns a domain for a given dataset as identified by a folder. If a
    time_unit is passed as a function parameter, the function will assume
    that the domain is periodic and with only return the min/max dates,
    otherwise ALL dates available for that dataset/spotlight will be returned.

    Params:
    ------
    dataset_folder (str): dataset folder to search within
    time_unit (Optional[str]): time_unit from the dataset's metadata json file
    spotlight_id (Optional[str]): a dictionary containing the
        `spotlight_id` of a spotlight to restrict the
        domain search to.
    time_unit (Optional[str] - one of ["day", "month"]):
        Wether the {date} object in the S3 filenames should be matched
        to YYYY_MM_DD (day) or YYYYMM (month)

    Return:
    ------
    List[datetime]
    """
    s3_keys_args: Dict[str, Any] = {"prefix": dataset_folder}
    if spotlight_id:
        s3_keys_args["spotlight_id"] = spotlight_id
    if dataset_bucket:
        s3_keys_args['dataset_bucket'] = dataset_bucket

    keys = _gather_s3_keys(**s3_keys_args)
    if not keys:
        raise NoKeysFoundForSpotlight

    dates = []

    for key in keys:

        # matches either dates like: YYYYMM or YYYY_MM_DD
        pattern = re.compile(
            r"[^a-zA-Z0-9]((?P<YEAR>\d{4})[_|.](?P<MONTH>\d{2})[_|.](?P<DAY>\d{2}))[^a-zA-Z0-9]"
        )
        if time_unit == "month":
            pattern = re.compile(
                r"[^a-zA-Z0-9](?P<YEAR>(\d{4}))(?P<MONTH>(\d{2}))[^a-zA-Z0-9]"
            )

        result = pattern.search(key, re.IGNORECASE,)

        if not result:
            continue

        date = None
        try:
            date = datetime.datetime(
                int(result.group("YEAR")),
                int(result.group("MONTH")),
                int(result.groupdict().get("DAY", 1)),
            )

        except ValueError:
            # Invalid date value matched - skip date
            continue

        # Some files happen to have 6 consecutive digits (likely an ID of sorts)
        # that sometimes gets matched as a date. This further restriction of
        # matched timestamps will reduce the number of "false" positives (although
        # ID's between 201011 and 203011 will slip by)
        if not datetime.datetime(2010, 1, 1) < date < datetime.datetime(2030, 1, 1):
            continue

        dates.append(date.strftime("%Y-%m-%dT%H:%M:%SZ"))

    if is_periodic and len(dates):
        return [min(dates), max(dates)]

    return sorted(set(dates))


class NoKeysFoundForSpotlight(Exception):
    """Exception to be thrown if no keys are found for a given spotlight"""

    pass

if __name__ == "__main__":
    json.dumps(handler({}, {}))
