"""
DynamoDB tables infrastructure stack.

This module defines DynamoDB tables for conversation history and
WebSocket connection management with encryption and backup settings.
"""

from aws_cdk import NestedStack, RemovalPolicy, Tags
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_kms as kms
from aws_cdk import aws_logs as logs
from constructs import Construct


class DynamoDBStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, websocket_table_name: str, conversation_table_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Create a KMS key for DynamoDB encryption
        self.dynamodb_encryption_key = kms.Key(
            self, "DynamoDBEncryptionKey",
            description="KMS key for DynamoDB table encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY,
            alias="bedrock-chatbot-dynamodb-key"
        )
        
        # Create DynamoDB table for conversation history
        self.conversation_table = dynamodb.Table(
            self, "ConversationTable",
            table_name=conversation_table_name,
            partition_key=dynamodb.Attribute(
                name="conversationId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER
            ),
            time_to_live_attribute="ttl",
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.dynamodb_encryption_key,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Add GSI for user_id
        self.conversation_table.add_global_secondary_index(
            index_name="UserIdIndex",
            partition_key=dynamodb.Attribute(
                name="userId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )
        
        # Create log groups
        logs.LogGroup(
            self, "DynamoDBTableLogs",
            log_group_name=f"/aws/dynamodb/{self.conversation_table.table_name}",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK
        )
        
        logs.LogGroup(
            self, "DynamoDBStreamsLogs",
            log_group_name=f"/aws/dynamodb/streams/{self.conversation_table.table_name}",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK
        )

        # Create DynamoDB table for WebSocket connections
        self.connections_table = dynamodb.Table(
            self, "ConnectionsTable",
            table_name=websocket_table_name,
            partition_key=dynamodb.Attribute(
                name="connectionId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.dynamodb_encryption_key,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            removal_policy=RemovalPolicy.DESTROY
        )

        # Apply tags to all resources in this stack
        Tags.of(self).add("Project", "BedrockChatbot")
        Tags.of(self).add("Environment", "Demo")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Application", "GenAI-MLflow-Orchestration")
        Tags.of(self).add("Component", "DynamoDB")

    # Property to expose the KMS key ARN
    @property
    def kms_key_arn(self) -> str:
        return self.dynamodb_encryption_key.key_arn
