# dashboard-api-starter

A lightweight API for Earthdata.

## Contributing data
More information for data contributors like expected input format and delivery mechanisms, can be found in the [data guidelines](guidelines/README.md).

## Local Environment

First, add your AWS credentials to a new file called `.env`. You can see an example of this file at `.env.example`.

### Clone and configure

```bash
git clone https://github.com/NASA-IMPACT/dashboard-api-starter.git
cd dashboard-api-starter
# Copy and configure the app
cp stack/config.yml.example stack/config.yml
```

Note, the local `stack/config.yml` file will only be used for running the app locally. Deployment to AWS is managed via CDK and github actions (See `.github/workflows/deploy.yml`).

Datasets for `/v1/datasets` are loaded from a json file stored in S3 unless `ENV=local` is set when running the app. The S3 location for these datasets is defined by the `BUCKET` and `DATASET_METADATA_FILENAME` values in `stack/config.yml`: `s3://{BUCKET}/{DATASET_METADATA_FILENAME}`.

### Running the app locally

You can use `ENV=local` when running the app locally to use the `example-dataset-metadata.json` file as the source for `/v1/datasets`. This is useful for testing new dataset configurations.

**NOTE:** Create if needed and ensure access to the bucket configured in `stack/config.yml`. When using github actions to deploy the API this config file is generated from `stack/config.yml.example` using the variables (including a bucket) defined there.

```bash
pyenv install
pip install -e .
# Create or add buckets for your data files
export AWS_PROFILE=CHANGEME
# Run the app with dataset metadata stored on S3
uvicorn dashboard_api.main:app --reload
# Run the app with example-dataset-metadata.json - useful for testing
ENV=local uvicorn dashboard_api.main:app --reload
```

Test the api `open http://localhost:8000/v1/datasets`

### Running the app with docker:

```bash
docker-compose up --build
```

Test the api `open http://localhost:8000/v1/datasets`

## Contribution & Development

Issues and pull requests are more than welcome.

## Metadata Generation

Metadata is used to list serve data via `/datasets`, `/tiles`, and `/timelapse`. Datasets are fetched from the bucket configured in `config.yml`. When using github actions to deploy the API this config file is generated from `stack/config.yml.example` using the variables (including a bucket) defined there. Assuming you are using the API with a repo based off of https://github.com/NASA-IMPACT/dashboard-datasets-starter/, you will want to configure `DATA_BUCKET` in deploy.yml to match what is deployed as a part of your datasets.repo.

## Automated Cloud Deployment via GitHub Actions

The file `.github/workflows/deploy.yml` describes how to deploy this service from GitHub Actions, and will
automatically try to do so. This requires a few secrets to be configured.  This deployment method is documented 
in greater detail [here](https://github.com/NASA-IMPACT/earthdata-dashboard-starter/wiki/Create-Your-Own-Dashboard).

### Build and deploy performance improvement with GitHub Actions (Optional, but recommended) 

By default, this service deploys using GitHub Actions. One limitation of GitHub Actions is the lack of a fast
and easy way to persist Docker image layers between executions. This means that each build starts with an empty
Docker layer cache. This is a particular problem for this build, as it requires several packages, notably numpy, 
to be built from source because binary packages for the lambda environment do not exist. This can take up to 
10 minutes. The way to get around this is to pre-build a Docker image with numpy from the lambda base image and use
this in the CI build.

1. Edit `Dockerfiles/lambda/Makefile` and replace the value of `IMG_NAME = PROJECT-dashboard-api-base` the the name of this project, e.g., `IMG_NAME = myproject-dashboard-api-base`
2. Create an ECR Repository with the name used for `IMG_NAME`, e.g., `aws ecr create-repository --repository-name myproject-dashboard-api-base --image-tag-mutability IMMUTABLE`
3. In directory `Dockerfiles/lambda`, run `make`. This should publish a new base image to the ECR repository.
4. Edit the `FROM` directive in `Dockerfiles/lambda/Dockerfile` to reference the new image in ECR.
5. Edit `deploy.sh` and uncomment the line that performs ECR login.
6. Commit all of these changes to GitHub and continue with the remaining configuration steps.

## Manual Cloud Deployment

### Requirements

* npm
* jq

### Install AWS CDK and pip requirements 

`./install.sh` should only be run once and if requirements set in `setup.py` change.

```bash
export AWS_PROFILE=CHANGEME
# Install requirements: aws-cdk and pip
# Bootstrap the account
# Should only need to run this once unless pip requirements change.
./install.sh
```

### Run CDK bootstrap

The CDK bootstrap command installs resources necessary to use CDK in your AWS account.

```bash
export AWS_PROFILE=CHANGEME
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile github-deploy | jq .Account -r)
export AWS_REGION=$(aws configure get region)
cdk bootstrap aws://$AWS_ACCOUNT_ID/$AWS_REGION --all
```

### Deploy

Deploy the app!

This currently deploys 2 stacks.

```bash
export AWS_PROFILE=CHANGEME
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity | jq .Account -r)
export AWS_REGION=$(aws configure get region)

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
# configure the API_URL to be the same (you might need to add `v1/` at the end) as returned from `./deploy.sh`
API_URL=<REPLACE_ME> yarn deploy
```
