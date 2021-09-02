# dashboard-api-starter

A lightweight tile server for COVID data, based on [titiler](https://github.com/developmentseed/titiler).

## Contributing data
More information for data contributors like expected input format and delivery mechanisms, can be found in the [data guidelines](guidelines/README.md).

## Local Environment

First, add your AWS credentials to a new file called `.env`. You can see an example of this file at `.env.example`.

### Clone and configure

```bash
git clone https://github.com/NASA-IMPACT/dashboard-api-starter.git
cd dashboard-api-starter

# Add your AWS credentials to a new file called `.env`. You can see an example of this file at `.env.example`.
cp .env.example .env
# Copy and configure the app
cp stack/config.yml.example stack/config.yml
```

**IMPORTANT:** Create if needed and ensure access to the buckets configured in `stack/config.yml`.

### Running the app locally

To run the app locally, generate a config file and generate the static dataset json files.

NOTE: This requires read and write access to the s3 bucket in `stack/config.yml`.

```bash
pyenv install
pip install -e .
# Create or add buckets for your data files
export AWS_PROFILE=CHANGEME
python -m lambda.dataset_metadata_generator.src.main
# Run the app
uvicorn dashboard_api.main:app --reload
```

Test the api `open http://localhost:8000/v1/datasets`

### Running the app with docker:

```bash
docker-compose up --build
```

Test the api `open http://localhost:8000/v1/datasets`

## Contribution & Development

Issues and pull requests are more than welcome.

### If developing on the appplication, use pre-commit

This repo is set to use `pre-commit` to run *my-py*, *flake8*, *pydocstring* and *black* ("uncompromising Python code formatter") when commiting new code.

```bash
$ pre-commit install
$ git add .
$ git commit -m'fix a really important thing'
black....................................................................Passed
Flake8...................................................................Passed
Verifying PEP257 Compliance..............................................Passed
mypy.....................................................................Passed
[precommit cc12c5a] fix a really important thing
 ```

### Modifying datasets

To modify the existing datasets, one can configure datasets to be listed by revising the list under

```yaml
DATASETS:
  STATIC:
```

in `stack/config.yml` and / or listing datasets from an external `STAC_API_URL`.

Metadata is used to list serve data via `/datasets`, `/tiles`, and `/timelapse` There are 2 possible sources of metadata for serving these resources.

1. Static JSON files, stored in `dashboard_api/db/static/datasets/`
2. STAC API, defined in `stack/config.yml`

In `lambda/dataset_metadata_generator` is code for a lambda to asynchronously generate metadata json files.

This lambda generates metadata in 2 ways:

1. Reads through the s3 bucket to generate a file that contains the datasets for each given spotlight option (_all, global, tk, ny, sf, la, be, du, gh) and their respective domain for each spotlight.
2. If `STAC_API_URL` is configured in `stack/config.yml`, fetches collections from a STAC catalogue and generates a metadata object for each collection.

## Cloud Deployment

Requirements:

* npm
* jq

### Install AWS CDK, pip requirements and run CDK bootstrap

`./install.sh` should only be run once and if requirements set in `setup.py` change.

```bash
export AWS_PROFILE=CHANGEME
# Install requirements: aws-cdk and pip
# Bootstrap the account
# Should only need to run this once unless pip requirements change.
./install.sh
```

Deploy the app!

This currently deploys 2 stacks.

```bash
export AWS_PROFILE=CHANGEME
# Note - the docker build is currently slow so this can take 5+ minutes to run 
./deploy.sh
```

Deploy the dashboard!

```bash
# Suggest changing your parent directory for distinct repository organization
cd ..
git clone git@github.com:NASA-IMPACT/earthdata-dashboard-starter.git
cd earthdata-dashboard-starter
nvm install
# configure the API_URL to be the same as returned from `./deploy.sh`
API_URL=<REPLACE_ME> yarn deploy
```