"""Construct App."""

import os
import shutil
from typing import Any

import config

# import docker
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_integrations as apigw_integrations
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticache as escache
from aws_cdk import aws_events, aws_events_targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda, aws_s3, core

s3_full_access_to_data_bucket = iam.PolicyStatement(
    actions=["s3:*"], resources=[f"arn:aws:s3:::{config.BUCKET}*"]
)

DEFAULT_ENV = dict(
    CPL_TMPDIR="/tmp",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    GDAL_CACHEMAX="75%",
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    GDAL_HTTP_MULTIPLEX="YES",
    GDAL_HTTP_VERSION="2",
    PYTHONWARNINGS="ignore",
    VSI_CACHE="TRUE",
    VSI_CACHE_SIZE="1000000",
)


class dashboardApiLambdaStack(core.Stack):
    """
    Dashboard Api Lambda Stack

    This code is freely adapted from
    - https://github.com/leothomas/titiler/blob/10df64fbbdd342a0762444eceebaac18d8867365/stack/app.py author: @leothomas
    - https://github.com/ciaranevans/titiler/blob/3a4e04cec2bd9b90e6f80decc49dc3229b6ef569/stack/app.py author: @ciaranevans

    """

    def __init__(
        self,
        scope: core.Construct,
        id: str,
        dataset_metadata_filename: str,
        memory: int = 1024,
        timeout: int = 30,
        concurrent: int = 100,
        code_dir: str = "./",
        **kwargs: Any,
    ) -> None:
        """Define stack."""
        super().__init__(scope, id, **kwargs)

        # add cache
        if config.VPC_ID:
            vpc = ec2.Vpc.from_lookup(self, f"{id}-vpc", vpc_id=config.VPC_ID,)
        else:
            vpc = ec2.Vpc(self, f"{id}-vpc")

        sb_group = escache.CfnSubnetGroup(
            self,
            f"{id}-subnet-group",
            description=f"{id} subnet group",
            subnet_ids=[sb.subnet_id for sb in vpc.private_subnets],
        )

        lambda_function_security_group = ec2.SecurityGroup(
            self, f"{id}-lambda-sg", vpc=vpc
        )
        lambda_function_security_group.add_egress_rule(
            ec2.Peer.any_ipv4(),
            connection=ec2.Port(protocol=ec2.Protocol("ALL"), string_representation=""),
            description="Allow lambda security group all outbound access",
        )

        cache_security_group = ec2.SecurityGroup(self, f"{id}-cache-sg", vpc=vpc)

        cache_security_group.add_ingress_rule(
            lambda_function_security_group,
            connection=ec2.Port(protocol=ec2.Protocol("ALL"), string_representation=""),
            description="Allow Lambda security group access to Cache security group",
        )

        cache = escache.CfnCacheCluster(
            self,
            f"{id}-cache",
            cache_node_type=config.CACHE_NODE_TYPE,
            engine=config.CACHE_ENGINE,
            num_cache_nodes=config.CACHE_NODE_NUM,
            vpc_security_group_ids=[cache_security_group.security_group_id],
            cache_subnet_group_name=sb_group.ref,
        )

        logs_access = iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            resources=["*"],
        )
        ec2_network_access = iam.PolicyStatement(
            actions=[
                "ec2:CreateNetworkInterface",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DeleteNetworkInterface",
            ],
            resources=["*"],
        )

        lambda_env = DEFAULT_ENV.copy()
        lambda_env.update(
            dict(
                MODULE_NAME="dashboard_api.main",
                VARIABLE_NAME="app",
                WORKERS_PER_CORE="1",
                LOG_LEVEL="error",
                MEMCACHE_HOST=cache.attr_configuration_endpoint_address,
                MEMCACHE_PORT=cache.attr_configuration_endpoint_port,
                DATASET_METADATA_FILENAME=dataset_metadata_filename,
            )
        )

        lambda_function_props = dict(
            runtime=aws_lambda.Runtime.PYTHON_3_7,
            code=self.create_package(code_dir),
            handler="handler.handler",
            memory_size=memory,
            timeout=core.Duration.seconds(timeout),
            environment=lambda_env,
            security_groups=[lambda_function_security_group],
            vpc=vpc,
        )

        if concurrent:
            lambda_function_props["reserved_concurrent_executions"] = concurrent

        lambda_function = aws_lambda.Function(
            self, f"{id}-lambda", **lambda_function_props
        )

        lambda_function.add_to_role_policy(s3_full_access_to_data_bucket)
        lambda_function.add_to_role_policy(logs_access)
        lambda_function.add_to_role_policy(ec2_network_access)

        # defines an API Gateway Http API resource backed by our "dynamoLambda" function.
        api = apigw.HttpApi(
            self,
            f"{id}-endpoint",
            default_integration=apigw_integrations.LambdaProxyIntegration(
                handler=lambda_function
            ),
        )
        core.CfnOutput(self, "API Endpoint", value=api.url)

    def create_package(self, code_dir: str) -> aws_lambda.Code:
        """Build docker image and create package."""

        return aws_lambda.Code.from_asset(
            path=os.path.abspath(code_dir),
            bundling=core.BundlingOptions(
                image=core.DockerImage.from_build(
                    path=os.path.abspath(code_dir),
                    file="Dockerfiles/lambda/Dockerfile",
                ),
                command=["bash", "-c", "cp -R /var/task/. /asset-output/."],
            ),
        )

app = core.App()


# Tag infrastructure
for key, value in {
    "Project": config.PROJECT_NAME,
    "Stack": config.STAGE,
    "Owner": os.environ.get("OWNER"),
    "Client": os.environ.get("CLIENT"),
}.items():
    if value:
        core.Tag.add(app, key, value)

lambda_stackname = f"{config.PROJECT_NAME}-lambda-{config.STAGE}"
dashboardApiLambdaStack(
    app,
    lambda_stackname,
    memory=config.MEMORY,
    timeout=config.TIMEOUT,
    concurrent=config.MAX_CONCURRENT,
    dataset_metadata_filename=f"{config.STAGE}-dataset-metadata.json",
    env=dict(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    ),
)

app.synth()
