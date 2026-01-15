"""
WebSocket API Gateway infrastructure stack.

This module defines the WebSocket API Gateway configuration with
routes for real-time chat communication and Lambda integrations.
"""

from aws_cdk import Aspects, CfnOutput, NestedStack, RemovalPolicy, Tags
from aws_cdk import aws_apigatewayv2 as apigatewayv2
from aws_cdk import aws_logs as logs
from aws_cdk.aws_apigatewayv2_integrations import WebSocketLambdaIntegration
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from constructs import Construct


class WebSocketApiStack(NestedStack):
    def __init__(
        self, scope: Construct, construct_id: str, lambda_function, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create WebSocket API 
        self.websocket_api = apigatewayv2.WebSocketApi(
            self,
            "ChatbotWebSocketAPI",
            api_name="bedrock-chatbot-websocket-api",
            description="WebSocket API for Bedrock Chatbot",
            route_selection_expression="$request.body.action",
            connect_route_options=apigatewayv2.WebSocketRouteOptions(
                integration=WebSocketLambdaIntegration(
                    "ConnectIntegration", lambda_function
                )
            ),
            disconnect_route_options=apigatewayv2.WebSocketRouteOptions(
                integration=WebSocketLambdaIntegration(
                    "DisconnectIntegration", lambda_function
                )
            ),
        )

        # Add custom route for sending messages
        self.websocket_api.add_route(
            "sendMessage",
            integration=WebSocketLambdaIntegration(
                "SendMessageIntegration", lambda_function
            ),
        )

        # Create WebSocket API stage without CloudWatch logging
        # Note: CloudWatch logging disabled to avoid account role requirement
        self.websocket_stage = apigatewayv2.WebSocketStage(
            self,
            "ChatbotWebSocketStage",
            web_socket_api=self.websocket_api,
            stage_name="dev",
            auto_deploy=True,
        )

        # Store outputs as properties
        api_endpoint = f"{self.websocket_api.api_id}.execute-api.{self.region}"
        stage_name = self.websocket_stage.stage_name
        self.api_url = f"wss://{api_endpoint}.amazonaws.com/{stage_name}"

        # Create outputs
        CfnOutput(
            self,
            "WebSocketAPIURL",
            value=self.api_url,
            description="WebSocket API URL",
            export_name=(f"{self.stack_name}-WebSocketAPIURL"),
        )

        # Apply tags to all resources in this stack
        Tags.of(self).add("Project", "BedrockChatbot")
        Tags.of(self).add("Environment", "Demo")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Application", "GenAI-MLflow-Orchestration")
        Tags.of(self).add("Component", "WebSocketAPI")

        # Apply CDK Nag suppressions at the stack level
        Aspects.of(self).add(AwsSolutionsChecks())

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-APIG4",
                    "reason": (
                        "This is for blog purposes only. In your environment, "
                        "make sure to use the specific policies of your "
                        "organization when deploying this solution like Cognito "
                        "or other authentication mechanisms would be implemented."
                    ),
                },
                {
                    "id": "AwsSolutions-APIG1",
                    "reason": (
                        "Access logging disabled to avoid CloudWatch Logs role "
                        "requirement. Enable logging in production environments "
                        "after configuring the appropriate IAM role."
                    ),
                },
            ],
        )
