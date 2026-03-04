"""
VPC and networking infrastructure stack.

This module defines the Virtual Private Cloud configuration with subnets,
security groups, and VPC endpoints for secure AWS service communication.
"""

from aws_cdk import Aspects, CfnOutput, NestedStack, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from constructs import Construct


class VpcStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, vpc_endpoint_security_group_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create VPC with consistent naming and flow logs
        self.vpc = ec2.Vpc(
            self,
            "ChatbotVPC",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
            flow_logs={
                "FlowLogCloudWatch": ec2.FlowLogOptions(
                    destination=ec2.FlowLogDestination.to_cloud_watch_logs(),
                    traffic_type=ec2.FlowLogTrafficType.ALL,
                )
            },
        )

        # Create security group for VPC endpoints with consistent naming
        self.endpoint_security_group = ec2.SecurityGroup(
            self,
            "EndpointSecurityGroup",
            vpc=self.vpc,
            description="Security group for VPC endpoints",
            allow_all_outbound=False,
            security_group_name=vpc_endpoint_security_group_name,
        )

        # Allow inbound HTTPS traffic
        self.endpoint_security_group.add_ingress_rule(
            ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            ec2.Port.tcp(443),
            "Allow HTTPS traffic from within VPC",
        )

        # Create Gateway endpoints
        self.s3_endpoint = self.vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
            ],
        )

        # Create DynamoDB Gateway endpoint 
        self.dynamodb_endpoint = self.vpc.add_gateway_endpoint(
            "DynamoDBEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
            subnets=[
                ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                )
            ],
        )

        # Add policy to allow all DynamoDB actions through the endpoint
        self.dynamodb_endpoint.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.AnyPrincipal()],
                actions=["dynamodb:*"],
                resources=["*"],
            )
        )

        # Define interface endpoints with their configurations
        interface_endpoints = {
            "SageMakerAPIEndpoint": ("sagemaker.api", True),
            "SageMakerRuntimeEndpoint": ("sagemaker.runtime", True),
            "CloudWatchLogsEndpoint": ("logs", True),
            "CloudWatchEndpoint": ("monitoring", True),
            "ECREndpoint": ("ecr.api", True),
            "ECRDockerEndpoint": ("ecr.dkr", True),
            "SecretsManagerEndpoint": ("secretsmanager", True),
            "SSMEndpoint": ("ssm", True),
            "SSMMessagesEndpoint": ("ssmmessages", True),
            "EC2MessagesEndpoint": ("ec2messages", True),
            "KMSEndpoint": ("kms", True),
            "BedrockEndpoint": ("bedrock", True),
            "BedrockRuntimeEndpoint": ("bedrock-runtime", True),
            "RDSEndpoint": ("rds", True),  # Added RDS endpoint
        }

        # Create interface endpoints
        self.vpc_endpoints = {}
        for endpoint_id, (service_name, private_dns) in interface_endpoints.items():
            try:
                self.vpc_endpoints[endpoint_id] = self.vpc.add_interface_endpoint(
                    endpoint_id,
                    service=ec2.InterfaceVpcEndpointAwsService(service_name),
                    private_dns_enabled=private_dns,
                    security_groups=[self.endpoint_security_group],
                    subnets=ec2.SubnetSelection(
                        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                    ),
                )
            except Exception as e:
                print(f"Failed to create endpoint {endpoint_id}: {str(e)}")
                continue

        # Store specific endpoints for reference
        self.bedrock_endpoint = self.vpc_endpoints.get("BedrockRuntimeEndpoint")
        self.bedrock_api_endpoint = self.vpc_endpoints.get("BedrockEndpoint")
        self.mlflow_endpoint = self.vpc_endpoints.get("SageMakerAPIEndpoint")
        self.secrets_manager_endpoint = self.vpc_endpoints.get("SecretsManagerEndpoint")
        self.rds_endpoint = self.vpc_endpoints.get("RDSEndpoint")

        # Add outputs for endpoints
        CfnOutput(
            self,
            "DynamoDBEndpointId",
            value=self.dynamodb_endpoint.vpc_endpoint_id,
            description="DynamoDB VPC Endpoint ID",
        )

        CfnOutput(
            self,
            "S3EndpointId",
            value=self.s3_endpoint.vpc_endpoint_id,
            description="S3 VPC Endpoint ID",
        )

        # Add outputs
        CfnOutput(self, "VpcId", value=self.vpc.vpc_id, description="VPC ID")

        CfnOutput(
            self,
            "PrivateSubnets",
            value=",".join(
                self.vpc.select_subnets(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                ).subnet_ids
            ),
            description="Private subnet IDs",
        )

        # Apply tags to all resources in this stack
        Tags.of(self).add("Project", "BedrockChatbot")
        Tags.of(self).add("Environment", "Demo")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Application", "GenAI-MLflow-Orchestration")
        Tags.of(self).add("Component", "VPC")

        # Apply CDK Nag suppressions at the stack level
        Aspects.of(self).add(AwsSolutionsChecks())

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "CdkNagValidationFailure",
                    "reason": "EC23 rule cannot be validated when CIDR block "
                    "is referenced using an intrinsic function.",
                }
            ],
        )
