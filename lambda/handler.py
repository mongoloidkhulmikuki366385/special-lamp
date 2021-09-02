"""AWS Lambda handler."""

from mangum import Mangum

from dashboard_api.main import app

handler = Mangum(app, enable_lifespan=False)
