"""sites endpoint."""

from dashboard_api.api import utils
from dashboard_api.db.static.sites import sites as sites_manager
from dashboard_api.db.memcache import CacheLayer
from dashboard_api.core import config
from dashboard_api.models.static import Site, Sites

from fastapi import APIRouter, Depends, HTTPException, Response, Request

router = APIRouter()


@router.get(
    "/sites",
    responses={200: dict(description="return a list of all available sites")},
    response_model=Sites,
)
def get_sites(
        request: Request,
        response: Response,
        cache_client: CacheLayer = Depends(utils.get_cache)):
    """Return list of sites."""
    sites_hash = utils.get_hash(site_id="_all")
    sites = None
    if cache_client:
        sites = cache_client.get_dataset_from_cache(sites_hash)
        if sites:
            response.headers["X-Cache"] = "HIT"
    if not sites:
        scheme = request.url.scheme
        host = request.headers["host"]
        if config.API_VERSION_STR:
            host += config.API_VERSION_STR

        sites = sites_manager.get_all(api_url=f"{scheme}://{host}")

        if cache_client and sites:
            cache_client.set_dataset_cache(sites_hash, sites, 60)

    return sites


@router.get(
    "/sites/{site_id}",
    responses={200: dict(description="return a site")},
    response_model=Site,
)
def get_site(
    request: Request,
    site_id: str,
    response: Response,
    cache_client: CacheLayer = Depends(utils.get_cache),
):
    """Return site info."""
    site_hash = utils.get_hash(site_id=site_id)
    site = None

    if cache_client:
        site = cache_client.get_dataset_from_cache(site_hash)

    if site:
        response.headers["X-Cache"] = "HIT"
    else:
        site = sites_manager.get(site_id, _api_url(request))
        if cache_client and site:
            cache_client.set_dataset_cache(site_hash, site, 60)

    if not site:
        raise HTTPException(
            status_code=404, detail=f"Non-existant site identifier: {site_id}"
        )

    return site
    

def _api_url(request: Request) -> str:
    scheme = request.url.scheme
    host = request.headers["host"]
    if config.API_VERSION_STR:
        host += config.API_VERSION_STR

    return f"{scheme}://{host}"
