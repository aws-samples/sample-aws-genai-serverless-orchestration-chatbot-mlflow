"""
Principal backend infrastructure stack.

This module defines the main backend deployment stack that coordinates all infrastructure
components including VPC, Lambda, RDS, DynamoDB, MLflow, and SageMaker resources.
"""

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

from stacks.database_stack import DatabaseStack
from stacks.dynamodb_stack import DynamoDBStack
from stacks.lambda_stack import LambdaStack
from stacks.mlflow_stack import MLflowStack
from stacks.sagemaker_base_stack import SageMakerBaseStack
from stacks.sagemaker_stack import SageMakerStack
from stacks.vpc_stack import VpcStack


class PrincipalBackendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Infrastructure components as nested stacks
        vpc_stack = VpcStack(
            self, "VpcStack",
            vpc_endpoint_security_group_name=config.VPC_ENDPOINT_SECURITY_GROUP_NAME
        )
        dynamodb_stack = DynamoDBStack(
            self, "DynamoDBStack",
            websocket_table_name=config.WEBSOCKET_TABLE_NAME,
            conversation_table_name=config.CONVERSATION_TABLE_NAME
        )
        database_stack = DatabaseStack(
            self, "DatabaseStack", 
            vpc=vpc_stack.vpc,
            database_name=config.DATABASE_NAME,
            database_port=config.DATABASE_PORT,
            database_instance_id=config.DATABASE_INSTANCE_ID
        )
        mlflow_stack = MLflowStack(
            self, "MLflowStack", 
            vpc=vpc_stack.vpc,
            mlflow_server_name=config.MLFLOW_SERVER_NAME,
            mlflow_version=config.MLFLOW_VERSION,
            mlflow_security_group_name=config.MLFLOW_SECURITY_GROUP_NAME
        )
        
        # SageMaker stacks
        sagemaker_base = SageMakerBaseStack(
            self, "SageMakerBaseStack",
            vpc=vpc_stack.vpc,
            kms_key_arn=dynamodb_stack.kms_key_arn,
            sagemaker_role_name=config.SAGEMAKER_ROLE_NAME
        )

        # Grant cross-stack permissions
        dynamodb_stack.dynamodb_encryption_key.grant_decrypt(sagemaker_base.sagemaker_role)
        dynamodb_stack.conversation_table.grant_read_write_data(sagemaker_base.sagemaker_role)

        # Lambda stack with dependencies
        self.lambda_stack = LambdaStack(
            self, "LambdaStack",
            vpc=vpc_stack.vpc,
            bedrock_endpoint=vpc_stack.bedrock_endpoint,
            mlflow_endpoint=vpc_stack.mlflow_endpoint,
            database=database_stack.database,
            database_security_group=database_stack.db_security_group,
            lambda_security_group=database_stack.lambda_security_group,
            conversation_table=dynamodb_stack.conversation_table,
            mlflow_tracking_server_id=mlflow_stack.tracking_server_id,
            mlflow_security_group=mlflow_stack.mlflow_security_group,
            mlflow_bucket=mlflow_stack.mlflow_bucket,
            database_name=config.DATABASE_NAME,
            database_port=config.DATABASE_PORT,
            lambda_memory_size=config.LAMBDA_MEMORY_SIZE,
            lambda_timeout_minutes=config.LAMBDA_TIMEOUT_MINUTES,
            websocket_table_name=config.WEBSOCKET_TABLE_NAME,
            chat_model_id=config.CHAT_MODEL_ID,
            mlflow_server_name=config.MLFLOW_SERVER_NAME
        )
        
        # Export Lambda function ARN for frontend integration
        CfnOutput(self, "BedrockChatbotFunctionArn",
                 value=self.lambda_stack.lambda_function.function_arn,
                 description="Bedrock Chatbot Lambda Function ARN")

        # Grant KMS access to Lambda
        dynamodb_stack.dynamodb_encryption_key.grant_decrypt(self.lambda_stack.lambda_function.role)

        # Configure security group rules for network access
        mlflow_stack.mlflow_security_group.add_ingress_rule(
            sagemaker_base.sagemaker_sg,
            ec2.Port.tcp(443),
            "Allow HTTPS access from SageMaker to MLflow"
        )

        database_stack.db_security_group.add_ingress_rule(
            sagemaker_base.sagemaker_sg,
            ec2.Port.tcp(5432),
            "Allow access from SageMaker Studio"
        )

        # SageMaker domain with MLflow integration
        sagemaker_domain = SageMakerStack(
            self, "SageMakerDomainStack",
            vpc=vpc_stack.vpc,
            base_stack=sagemaker_base,
            mlflow_tracking_server_id=mlflow_stack.tracking_server_id,
            sagemaker_domain_name=config.SAGEMAKER_DOMAIN_NAME,
            sagemaker_user_profile_name=config.SAGEMAKER_USER_PROFILE_NAME
        )

        # Define explicit dependencies for proper deployment order
        self.lambda_stack.node.add_dependency(vpc_stack)
        self.lambda_stack.node.add_dependency(database_stack)
        self.lambda_stack.node.add_dependency(dynamodb_stack)
        self.lambda_stack.node.add_dependency(mlflow_stack)
        
        sagemaker_base.node.add_dependency(vpc_stack)
        sagemaker_domain.node.add_dependency(mlflow_stack)
        sagemaker_domain.node.add_dependency(sagemaker_base)
        
        # Export SageMaker Domain ID
        CfnOutput(self, "SageMakerDomainId",
                 value=sagemaker_domain.domain.attr_domain_id,
                 description="SageMaker Domain ID")
