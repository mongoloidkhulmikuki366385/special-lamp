"""sites endpoint."""

from dashboard_api.db.static.sites import SiteNames, sites
from dashboard_api.models.static import Site, Sites

from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/sites",
    responses={200: dict(description="return a list of all available sites")},
    response_model=Sites,
)
def get_sites():
    """Return list of sites."""
    return sites.get_all()


@router.get(
    "/sites/{id}",
    responses={200: dict(description="return a site")},
    response_model=Site,
)
def get_site(id: SiteNames):
    """Return site info."""
    return sites.get(id.value)
