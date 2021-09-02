""" Dataset metadata generator lambda. """
import datetime
import json
import os
import re
import requests
from typing import Any, Dict, List, Optional, Union
import yaml

import boto3

from rio_tiler.io import COGReader
from cogeo_mosaic.mosaic import MosaicJSON

BASE_PATH = os.path.abspath('.')
config = yaml.load(open(f"{BASE_PATH}/stack/config.yml", 'r'), Loader=yaml.FullLoader)

DATASETS_JSON_FILEPATH = os.path.join(BASE_PATH, "dashboard_api/db/static/datasets")

DATASET_METADATA_FILENAME = os.environ.get("DATASET_METADATA_FILENAME", config.get('DATASET_METADATA_FILENAME'))
STAC_API_URL = config['STAC_API_URL']

s3 = boto3.resource("s3")
bucket = s3.Bucket(os.environ.get("DATA_BUCKET_NAME", config.get('BUCKET')))

DT_FORMAT = "%Y-%m-%d"
MT_FORMAT = "%Y%m"

# Can test this with ENV=local python -m lambda.dataset_metadata_generator.src.main | jq .
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
        GET /datasets/global)
    """

    # TODO: defined TypedDicts for these!
    datasets_to_parse = config['DATASETS']
    datasets = _gather_dataset_configurations(DATASETS_JSON_FILEPATH, selections=datasets_to_parse)

    # TODO: only use items which can be visualized
    # if STAC_API_URL:
    #     stac_datasets = _fetch_stac_items()
    #     datasets.extend(stac_datasets)

    result = _gather_datasets_metadata(datasets)
    # TODO: Protect from running _not_ in "production" deployment
    bucket.put_object(
        Body=json.dumps(result), Key=DATASET_METADATA_FILENAME, ContentType="application/json",
    )
    if os.environ.get('ENV') == 'local':
        print('IN LOCAL')
        with open('example-dataset-metadata.json', 'w') as f:
            f.write(json.dumps(result, indent=2))
            f.close()
    return result

def _dateset_metadata_template():
    return {
        "id": "",
        "name": "",
        "type": "raster",
        "time_unit": "",
        "is_periodic": Flase,
        "source": {
            "type": "raster",
            # For now, don't list any tiles. We will want to mosaic STAC search results.
            "tiles": []
        },
        "info": "",
    }

TITILER_ENDPOINT = "https://api.cogeo.xyz"
username = "aimee-dashboard-api"

def create_token():
    r = requests.post(
        f"{TITILER_ENDPOINT}/tokens/create",
        json={
            "username": username,
            "scope": ["mosaic:read", "mosaic:create"]
        }
    ).json()
    return r["token"]

def post_mosaic(mosaicdata, token, layername):
    r = requests.post(
        f"{TITILER_ENDPOINT}/mosaicjson/upload",
        json={
            "username": username,
            "layername": layername,
            "mosaic": mosaicdata.dict(exclude_none=True),
            "overwrite": True
        },
        params={
            "access_token": token,
        }
    )
    return r.json()


def _create_mosaic_layer(stac_endpoint, collection_id):
    items = requests.get(stac_endpoint).json()
    features = items['features']
    # Creating a mosaic using cogeo_mosaic requires a path property
    for feature in features:
        # note this could be "assets: browse:" for STAC CMR :/
        feature['properties']['path'] = feature['assets']['visual']['href']
    now = datetime.datetime.now()
    first_cog = features[0]['assets']['visual']['href']
    with COGReader(first_cog) as cog:
        info = cog.info()
    # We are creating the mosaicJSON using the features we created earlier
    # by default MosaicJSON.from_feature will look in feature.properties.path to get the path of the dataset
    layername = f"{collection_id}_{now.strftime('%Y%m%d%H%M%S')}"
    mosaicdata = MosaicJSON.from_features(features, minzoom=info.minzoom, maxzoom=info.maxzoom)
    token = create_token()
    response = post_mosaic(mosaicdata, token, layername)
    layer = response['mosaic']
    r = requests.get(
        f"{TITILER_ENDPOINT}/mosaicjson/{username}.{layername}/tilejson.json",
    ).json()
    return r["tiles"][0]


# def _fetch_stac_items():
#     """ Fetches collections from a STAC catalogue and generates a metadata object for each collection. """
#     stac_response = requests.get(f"{STAC_API_URL}/collections")
#     if stac_response.status_code == 200:
#         stac_collections = json.loads(stac_response.content).get('collections')
#     stac_datasets = []
#     for collection in stac_collections:
#         # TODO: defined TypedDicts for these!

#         stac_dataset = _dateset_metadata_template.copy()
#         stac_dataset['id'] = collection['id']
#         stac_dataset['name'] = collection['title']
#         # TODO: pull dynamically
#         stac_dataset['time_unit'] = "day"
#         stac_dataset['info'] = collection['description']
#         stac_dataset['source'] = {
#             "type": "raster",
#             "tiles": [ "{api_url}/{z}/{x}/{y}@1x?url={tif_location}&resampling_method=nearest&bidx=1&rescale=-0.20000000298023224%2C0.9945999979972839&color_map=gist_earth" ]
#         }
#         stac_datasets.append(stac_dataset)

#     return stac_datasets

def _gather_datasets_metadata(datasets: List[dict]):
    """Reads through the s3 bucket to generate the respective time domain

    Params:
    -------
    datasets (List[dict]): list of dataset metadata objects (contains fields
        like: s3_location, time_unit, swatch, exclusive_with, etc), to use
        to generate the result of each of the possible `/datasets` endpoint
        queries.

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
        if dataset.get("source") and dataset.get("source").get("type") == 'STAC':
            # create mosaic using parameters
            stac_endpoint = f"{dataset.get('source').get('endpoint')}?"
            for param in dataset.get("source").get("params").items():
                stac_endpoint = f"{stac_endpoint}&{param[0]}={param[1]}"
            mosaic_tiles_url = _create_mosaic_layer(stac_endpoint, dataset.get('id'))
            dataset['source']['type'] = 'raster'
            dataset['source']['tiles'] = [ mosaic_tiles_url ]
        metadata.setdefault("_all", {}).update({dataset["id"]: dataset})
    return metadata


def _gather_dataset_configurations(dirpath: str, selections: List[str] = None) -> List[dict]:
    """Gathers all JSON files from within a diven directory"""

    results = []
    for filename in os.listdir(dirpath):
        if filename in selections:
            with open(os.path.join(dirpath, filename)) as f:
                if filename.endswith(".json"):
                    results.append(json.load(f))
                if filename.endswith(".yml"):
                    results.append(yaml.load(f, Loader=yaml.FullLoader))
    return results


def _gather_s3_keys(
    prefix: Optional[str] = "",
    dataset_bucket: Optional[str] = None
) -> List[str]:
    """
    Returns a set of S3 keys. If no args are provided, the keys will represent
    the entire S3 bucket.
    Params:
    -------
    prefix (Optional[str]):
        S3 Prefix under which to gather keys, used to specifcy a specific
        dataset folder to search within.

    Returns:
    -------
    set(str)

    """
    s3_dataset_bucket = bucket if dataset_bucket == None else s3.Bucket(dataset_bucket)

    keys = [x.key for x in s3_dataset_bucket.objects.filter(Prefix=prefix)]

    return keys


def _get_dataset_domain(
    dataset_folder: str,
    is_periodic: bool,
    dataset_bucket: Optional[str] = None,
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
    time_unit (Optional[str] - one of ["day", "month"]):
        Wether the {date} object in the S3 filenames should be matched
        to YYYY_MM_DD (day) or YYYYMM (month)

    Return:
    ------
    List[datetime]
    """
    s3_keys_args: Dict[str, Any] = {"prefix": dataset_folder}
    if dataset_bucket:
        s3_keys_args['dataset_bucket'] = dataset_bucket

    dates = []

    keys = _gather_s3_keys(**s3_keys_args)
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


if __name__ == "__main__":
    json.dumps(handler({}, {}))
