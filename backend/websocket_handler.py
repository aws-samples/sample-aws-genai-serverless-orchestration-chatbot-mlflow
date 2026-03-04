"""
WebSocket API event handler for real-time chat communication.

This module handles WebSocket lifecycle events ($connect, $disconnect, sendMessage)
and manages persistent connections through DynamoDB for the Bedrock chatbot.
"""

import json
import logging
import os
import time
import warnings
from functools import lru_cache
from typing import Any
from typing import Dict

import app
import boto3
import mlflow
from utils.utils import extract_reply


# Disable MLflow dataset source warnings
warnings.filterwarnings('ignore', category=UserWarning, module='mlflow.data.dataset_source_registry')
# Disable MLflow telemetry
os.environ['MLFLOW_ENABLE_TELEMETRY'] = 'false'

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize API Gateway Management API client
apigateway_management = boto3.client('apigatewaymanagementapi')

@lru_cache(maxsize=1)
def initialize_mlflow() -> bool:
    """Initialize MLflow configuration"""
    try:
        logger.info("Starting MLflow initialization")
        start_time = time.time()
        
        mlflow_arn = os.environ.get("MLFLOW_TRACKING_ARN")
        if not mlflow_arn:
            logger.warning("MLFLOW_TRACKING_ARN not set")
            return False
            
        logger.info(f"Initializing MLflow with ARN: {mlflow_arn}")
        mlflow.set_tracking_uri(mlflow_arn)
        
        # Only enable required autologging features
        mlflow.langchain.autolog(
            log_models=False,
            log_input_examples=False,
            log_model_signatures=False
        )
        
        logger.info(f"MLflow initialization completed in: {time.time() - start_time:.2f}s")
        return True
    except Exception as e:
        logger.error(f"Error initializing MLflow: {e}")
        return False

# Initialize MLflow at module level
MLFLOW_INITIALIZED = initialize_mlflow()

def get_connection_table():
    """Get DynamoDB table for storing WebSocket connections"""
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('CONNECTIONS_TABLE', 'websocket-connections')
    return dynamodb.Table(table_name)

def send_to_connection(connection_id: str, data: dict, endpoint_url: str):
    """Send data to a specific WebSocket connection"""
    try:
        # Create client with the specific endpoint
        client = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)
        
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data)
        )
        return True
    except client.exceptions.GoneException:
        logger.info(f"Connection {connection_id} is gone")
        # Remove from connection table
        try:
            table = get_connection_table()
            table.delete_item(Key={'connectionId': connection_id})
        except Exception as e:
            logger.error(f"Error removing connection {connection_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending to connection {connection_id}: {e}")
        return False

def connect_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle WebSocket connection"""
    try:
        connection_id = event['requestContext']['connectionId']
        
        # Store connection in DynamoDB
        table = get_connection_table()
        table.put_item(
            Item={
                'connectionId': connection_id,
                'timestamp': int(time.time()),
                'ttl': int(time.time()) + (3600 * 24)  # 24 hours TTL
            }
        )
        
        logger.info(f"Connection established: {connection_id}")
        return {'statusCode': 200}
        
    except Exception as e:
        logger.error(f"Error in connect handler: {str(e)}")
        return {'statusCode': 500}

def disconnect_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle WebSocket disconnection"""
    try:
        connection_id = event['requestContext']['connectionId']
        
        # Remove connection from DynamoDB
        table = get_connection_table()
        table.delete_item(Key={'connectionId': connection_id})
        
        logger.info(f"Connection disconnected: {connection_id}")
        return {'statusCode': 200}
        
    except Exception as e:
        logger.error(f"Error in disconnect handler: {str(e)}")
        return {'statusCode': 500}

def message_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle WebSocket messages - main chatbot logic"""
    try:
        start_time = time.time()
        connection_id = event['requestContext']['connectionId']
        endpoint_url = f"https://{event['requestContext']['domainName']}/{event['requestContext']['stage']}"
        
        # MLflow is already initialized at module level
        if not MLFLOW_INITIALIZED:
            logger.warning("MLflow initialization failed, continuing without MLflow")
        
        # Parse message body
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError:
            error_msg = {'type': 'error', 'message': 'Invalid JSON in message body'}
            send_to_connection(connection_id, error_msg, endpoint_url)
            return {'statusCode': 400}
        
        input_text = body.get('input')
        session_id = body.get('session_id')
        
        # Generate a session ID if none was provided
        if session_id is None:
            session_id = f"ws-session-{connection_id}-{int(time.time())}"
            logger.info(f"Generated new session_id: {session_id}")
        
        if not input_text:
            error_msg = {'type': 'error', 'message': 'No input provided'}
            send_to_connection(connection_id, error_msg, endpoint_url)
            return {'statusCode': 400}
        
        # Send acknowledgment that we received the message
        ack_msg = {
            'type': 'status', 
            'message': 'Processing your request...', 
            'session_id': session_id
        }
        send_to_connection(connection_id, ack_msg, endpoint_url)
        
        # Create session dictionary
        session_dict = {'session_id': session_id}
        
        logger.info(f"Processing message for session: {session_id}")
        
        # Set MLflow experiment if available
        try:
            if os.environ.get("MLFLOW_TRACKING_ARN"):
                mlflow.set_experiment(str(session_id))
        except Exception as e:
            logger.warning(f"Failed to set MLflow experiment: {e}")
        
        # Call the app to process the message
        response = app.execute_workflow(
            task=input_text,
            session_dict=session_dict
        )
        
        # Get the raw response
        raw_response = response.get('response', 'No response received')
        
        # Use extract_reply utility function
        clean_response = extract_reply(raw_response)
        
        # If extract_reply returns None, fall back to the raw response
        if clean_response is None:
            clean_response = raw_response
            
        # If response is empty or None, provide a fallback message
        if not clean_response or clean_response.strip() == '':
            clean_response = "I apologize, but I'm having trouble processing your request right now. Could you please try again?"
        
        # Calculate processing time
        processing_time = time.time() - start_time
        logger.info(f"Processing completed in: {processing_time:.2f}s")
        
        # Send the response back through WebSocket
        response_msg = {
            'type': 'response',
            'response': str(clean_response),
            'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            'session_id': session_id,
            'processing_time': round(processing_time, 2)
        }
        
        logger.info(f"Sending response: {response_msg}")
        success = send_to_connection(connection_id, response_msg, endpoint_url)
        logger.info(f"Response sent successfully: {success}")
        
        if success:
            return {'statusCode': 200}
        else:
            return {'statusCode': 410}  # Gone - connection no longer exists
            
    except Exception as e:
        logger.error(f"Error processing WebSocket message: {str(e)}", exc_info=True)
        
        try:
            error_msg = {
                'type': 'error',
                'message': 'An unexpected error occurred. Please try again.',
                'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            send_to_connection(connection_id, error_msg, endpoint_url)
        except Exception as send_err:
            logger.warning(
                "Failed to send error message to connection: %s", send_err
            )
            
        return {'statusCode': 500}

# Handler routing based on route key
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main WebSocket handler that routes to appropriate sub-handler"""
    route_key = event['requestContext']['routeKey']
    
    if route_key == '$connect':
        return connect_handler(event, context)
    elif route_key == '$disconnect':
        return disconnect_handler(event, context)
    elif route_key == 'sendMessage':
        return message_handler(event, context)
    else:
        logger.error(f"Unknown route key: {route_key}")
        return {'statusCode': 400}
