"""
Principal frontend infrastructure stack.

This module defines the main frontend deployment stack that coordinates
WebSocket API and React frontend hosting with S3 and CloudFront.
"""

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from stacks.frontend_stack import FrontendStack
from stacks.runtime_config_stack import RuntimeConfigStack
from stacks.websocket_api_stack import WebSocketApiStack


class PrincipalFrontendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str,
                 lambda_arn: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Import the Lambda function from ARN
        lambda_function = lambda_.Function.from_function_attributes(
            self, "ImportedLambda",
            function_arn=lambda_arn,
            same_environment=True
        )

        # Create WebSocket API stack as a nested stack
        websocket_api_stack = WebSocketApiStack(
            self,
            "WebSocketApiStack",
            lambda_function=lambda_function
        )

        # Create Web Hosting stack with WebSocket API as a nested stack
        web_hosting_stack = FrontendStack(
            self,
            "WebHostingStack",
            lambda_arn=lambda_arn,
            api=websocket_api_stack.websocket_api
        )

        # Generate config.json with actual WebSocket API URL
        RuntimeConfigStack(
            self,
            "RuntimeConfigStack",
            website_bucket=web_hosting_stack.website_bucket,
            api_url=websocket_api_stack.api_url
        )

        # Export outputs
        CfnOutput(self, "WebsiteURL",
                  value=web_hosting_stack.distribution.domain_name,
                  description="Website URL")

        CfnOutput(self, "WebSocketAPIURL",
                  value=websocket_api_stack.api_url,
                  description="WebSocket API URL",
                  export_name=f"{self.stack_name}-WebSocketAPIURL")

        CfnOutput(self, "WebsiteBucketName",
                  value=web_hosting_stack.website_bucket.bucket_name,
                  description="S3 bucket name for the website",
                  export_name=f"{self.stack_name}-WebsiteBucketName")