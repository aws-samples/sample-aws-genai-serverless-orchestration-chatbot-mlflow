"""
Main Lambda handler that routes different event types to appropriate handlers.
This is the entry point for the Lambda function.
"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler that routes WebSocket API events.
    
    Event Types:
    WebSocket API events (connect, disconnect, sendMessage)
    """
    try:
        logger.info(f"Received event: {json.dumps(event, default=str)}")
        
        # Check if this is a WebSocket API event
        if 'requestContext' in event and 'routeKey' in event['requestContext']:
            logger.info(f"Processing WebSocket event: {event['requestContext']['routeKey']}")
            from websocket_handler import handler as websocket_handler
            return websocket_handler(event, context)
        
        # Unknown event type
        else:
            logger.error(f"Unknown event type: {event}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Unknown event type'})
            }
            
    except Exception as e:
        logger.error(f"Error in main handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }
