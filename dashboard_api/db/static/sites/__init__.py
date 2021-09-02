""" dashboard_api static sites """
import os
import json

import botocore
from cachetools import TTLCache
from typing import Optional

from dashboard_api.db.utils import s3_get
from dashboard_api.models.static import Sites, Link
from dashboard_api.core.config import (SITE_METADATA_FILENAME, BUCKET)
from dashboard_api.db.utils import indicator_exists, indicator_folders
from dashboard_api.models.static import Site, Sites

class SiteManager(object):
    """Default Site holder."""

    def __init__(self):
        self.sites_cache = TTLCache(1, 60)

    def get(self, identifier: str, api_url: str) -> Optional[Site]:
        """Fetch a Site."""
        sites = self.get_all(api_url)
        return next(filter(lambda x: x.id == identifier, sites.sites), None)

    def get_all(self, api_url: str) -> Sites:
        """Fetch all Sites."""

        sites = self.sites_cache.get("sites")

        if sites:
            cache_hit = True
        else:
            cache_hit = False
            if os.environ.get('ENV') == 'local':
                # Useful for local testing
                example_sites = "example-site-metadata.json"
                print(f"Loading {example_sites}")
                s3_datasets = json.loads(open(example_sites).read())
                sites = Sites(**s3_datasets)
            else:    
                try:
                    print(f"Loading s3{BUCKET}/{SITE_METADATA_FILENAME}")
                    s3_datasets = json.loads(
                        s3_get(bucket=BUCKET, key=SITE_METADATA_FILENAME)
                    )
                    print("sites json successfully loaded from S3")

                except botocore.errorfactory.ClientError as e:
                    if e.response["Error"]["Code"] in ["ResourceNotFoundException", "NoSuchKey"]:
                        s3_datasets = json.loads(open("example-site-metadata.json").read())
                    else:
                        raise e

            sites = Sites(**s3_datasets)

            indicators = indicator_folders()

            for site in sites.sites:
                site.links.append(Link(
                    href=f"{api_url}/sites/{site.id}",
                    rel="self",
                    type="application/json",
                    title="Self"
                ))
                site.indicators = [ind for ind in indicators if indicator_exists(site.id, ind)]

        if not cache_hit and sites:
            self.sites_cache["sites"] = sites

        return sites


sites = SiteManager()
