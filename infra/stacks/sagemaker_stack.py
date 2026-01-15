# stacks/sagemaker_stack.py
from aws_cdk import (
    NestedStack,
    aws_ec2 as ec2,
    aws_sagemaker as sagemaker,
    CfnOutput,
    RemovalPolicy,
    Tags,
)
from constructs import Construct


class SageMakerStack(NestedStack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc,
        base_stack,
        mlflow_tracking_server_id,
        sagemaker_domain_name: str,
        sagemaker_user_profile_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # SageMaker domain with VPC configuration
        self.domain = sagemaker.CfnDomain(
            self,
            "SageMakerDomain",
            auth_mode="IAM",
            domain_name=sagemaker_domain_name,
            vpc_id=vpc.vpc_id,
            subnet_ids=vpc.select_subnets(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ).subnet_ids,
            app_network_access_type="VpcOnly",
            default_user_settings=sagemaker.CfnDomain.UserSettingsProperty(
                execution_role=base_stack.sagemaker_role.role_arn,
                security_groups=[base_stack.sagemaker_sg.security_group_id],
            ),
        )

        # Default user profile
        self.user_profile = sagemaker.CfnUserProfile(
            self,
            "DefaultUserProfile",
            domain_id=self.domain.attr_domain_id,
            user_profile_name=sagemaker_user_profile_name,
        )

        # Set removal policies for clean deletion
        self.domain.apply_removal_policy(RemovalPolicy.DESTROY)
        self.user_profile.apply_removal_policy(RemovalPolicy.DESTROY)

        # Output domain and user information
        CfnOutput(
            self,
            "SageMakerDomainId",
            value=self.domain.attr_domain_id,
            description="SageMaker Domain ID",
        )

        CfnOutput(
            self,
            "SageMakerUserProfile",
            value=self.user_profile.user_profile_name,
            description="SageMaker User Profile Name",
        )

        # Apply tags to all resources in this stack
        Tags.of(self).add("Project", "BedrockChatbot")
        Tags.of(self).add("Environment", "Demo")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Application", "GenAI-MLflow-Orchestration")
        Tags.of(self).add("Component", "SageMakerDomain")
