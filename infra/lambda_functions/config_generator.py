"""
Lambda function to generate config.json for React app.

This function creates the runtime configuration file with the actual WebSocket API URL
and uploads it to the S3 bucket hosting the React application.
"""

import json
import os
from typing import Any, Dict, Optional

import boto3
import urllib3


def send_response(
    event: Dict[str, Any],
    context: Any,
    response_status: str,
    response_data: Optional[Dict[str, Any]] = None,
    physical_resource_id: Optional[str] = None,
    reason: Optional[str] = None,
):
    """Send response back to CloudFormation."""
    response_data = response_data or {}

    response_body = {
        "Status": response_status,
        "Reason": reason or (
            f"See CloudWatch Log Stream: {context.log_stream_name}"
        ),
        "PhysicalResourceId": (
            physical_resource_id or context.log_stream_name
        ),
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": response_data,
    }

    json_response_body = json.dumps(response_body)
    print(f"Response body: {json_response_body}")

    headers = {
        "content-type": "",
        "content-length": str(len(json_response_body))
    }

    try:
        http = urllib3.PoolManager()
        response = http.request(
            "PUT",
            event["ResponseURL"],
            body=json_response_body,
            headers=headers
        )
        print(f"Status code: {response.status}")
    except Exception as e:
        print(f"Failed to send response to CloudFormation: {str(e)}")


def handler(event: Dict[str, Any], context: Any) -> None:
    """
    Lambda function to generate config.json and upload to S3.

    This function is triggered by CloudFormation custom resource events
    and generates the runtime configuration for the React app.
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        request_type = event.get("RequestType")

        if request_type in ["Create", "Update"]:
            # Get environment variables
            bucket_name = os.environ["BUCKET_NAME"]
            api_url = os.environ["API_URL"]
            region = os.environ["REGION"]

            # Create config.json content
            config = {
                "API_URL": api_url,
                "REGION": region,
                "API_KEY": None,  # WebSocket API doesn't use API keys
            }

            # Upload to S3
            s3_client = boto3.client("s3")
            s3_client.put_object(
                Bucket=bucket_name,
                Key="config.json",
                Body=json.dumps(config, indent=2),
                ContentType="application/json",
                CacheControl="no-cache,no-store,must-revalidate",
            )

            print(f"Successfully uploaded config.json to {bucket_name}")
            print(f"Config content: {json.dumps(config, indent=2)}")

            # Send success response to CloudFormation
            send_response(
                event,
                context,
                "SUCCESS",
                {
                    "ConfigUrl": (
                        f"https://{bucket_name}.s3.amazonaws.com/config.json"
                    ),
                    "ApiUrl": api_url,
                },
                f"config-generator-{bucket_name}",
            )

        elif request_type == "Delete":
            # Clean up config.json on stack deletion
            try:
                bucket_name = os.environ["BUCKET_NAME"]
                s3_client = boto3.client("s3")
                s3_client.delete_object(Bucket=bucket_name, Key="config.json")
                print(f"Deleted config.json from {bucket_name}")
            except Exception as e:
                print(f"Error deleting config.json: {str(e)}")

            # Send success response to CloudFormation
            send_response(
                event,
                context,
                "SUCCESS",
                {},
                f"config-generator-{os.environ.get('BUCKET_NAME', 'unknown')}",
            )

        else:
            # Unknown request type
            send_response(event, context, "SUCCESS", {}, "config-generator-unknown")

    except Exception as e:
        print(f"Error in handler: {str(e)}")
        # Send failure response to CloudFormation
        send_response(
            event, context, "FAILED", {}, "config-generator-failed", str(e)
        )
