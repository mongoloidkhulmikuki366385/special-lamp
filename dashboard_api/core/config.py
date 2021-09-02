"""Config."""

import os

import yaml

config_object = yaml.load(
    open(f"{os.path.abspath('.')}/stack/config.yml", "r"), Loader=yaml.FullLoader
)

STAGE = os.environ.get("STAGE", config_object["STAGE"])
VECTOR_TILESERVER_URL = os.environ.get(
    "VECTOR_TILESERVER_URL",
    config_object.get("VECTOR_TILESERVER_URL")
) or ""
TITILER_SERVER_URL = os.environ.get(
    "TITILER_SERVER_URL",
    config_object.get("TITILER_SERVER_URL")
) or ""
API_VERSION_STR = "/v1"

PROJECT_NAME = config_object["PROJECT_NAME"]

SERVER_NAME = os.getenv("SERVER_NAME")
SERVER_HOST = os.getenv("SERVER_HOST")
BACKEND_CORS_ORIGINS = os.getenv(
    "BACKEND_CORS_ORIGINS", default="*"
)  # a string of origins separated by commas, e.g: "http://localhost, http://localhost:4200, http://localhost:3000, http://localhost:8080, http://local.dockertoolbox.tiangolo.com"

DISABLE_CACHE = os.getenv("DISABLE_CACHE")
MEMCACHE_HOST = os.environ.get("MEMCACHE_HOST")
MEMCACHE_PORT = int(os.environ.get("MEMCACHE_PORT", 11211))
MEMCACHE_USERNAME = os.environ.get("MEMCACHE_USERNAME")
MEMCACHE_PASSWORD = os.environ.get("MEMCACHE_PASSWORD")

BUCKET = os.environ.get("BUCKET", config_object["BUCKET"])

DATASET_METADATA_FILENAME = os.environ.get(
    "DATASET_METADATA_FILENAME", config_object["DATASET_METADATA_FILENAME"]
)

SITE_METADATA_FILENAME = os.environ.get(
    "SITE_METADATA_FILENAME", config_object["SITE_METADATA_FILENAME"]
)

DT_FORMAT = "%Y-%m-%d"
MT_FORMAT = "%Y%m"
