"""
Entry point node for conversation processing.

This module handles initial message processing, intent classification,
and order information extraction from user inputs.
"""

import json
import logging
import os
import sys
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

import mlflow
from dotenv import load_dotenv
from langgraph.graph import END
from mlflow.entities import SpanType
from static import static

# from backend import tools_config
from tools_config.entry_intent_tool import tool_config as entry_intent_tool_config
from utils import utils


# Get the absolute path to the backend directory
current_dir = os.getcwd()  # Get current working directory
backend_path = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(backend_path)

# Load environment variables from .env file
load_dotenv()

# configure logging
logger = logging.getLogger()
logger.setLevel("INFO")


@mlflow.trace(span_type=SpanType.AGENT)
def node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Entry intent node for processing chat messages and managing order information.

    This node handles:
    1. Initial message processing with the chat model
    2. Tool execution for order information retrieval
    3. State management and updates
    4. Dynamic routing based on order information

    Args:
        state (Dict[str, Any]): The current state dictionary containing:
            - session_id: Unique identifier for the session
            - messages: List of conversation messages
            - transcript: List of conversation history
            - other dynamic state variables

    Returns:
        Dict[str, Any]: Updated state dictionary containing:
            - messages: Updated conversation messages
            - transcript: Updated conversation history
            - order_number: Order ID if found
            - order_info_found: Boolean indicating if order was found
            - next_node: Next node in the conversation flow
            - other state variables

    Raises:
        JSONDecodeError: If tool response parsing fails
        KeyError: If required keys are missing in the response
        IndexError: If response structure is invalid
    """
    print('\n <============== Node: entry_intent ===================> \n')
    session_id = state.get('session_id')
    messages = state.get('messages', [])
    transcript = state.get('transcript', [])

    # Configure API call parameters
    inference_config = {
        "temperature": static.TEMPERATURE, 
        "maxTokens": static.MAX_TOKENS
    }
    additional_model_fields = {
        "top_k": static.TOP_K
    }
    request_metadata = {
        'string': 'string'
    }

    # Process message
    response, message, stop_reason = utils.process_message(
        messages=messages,
        model_id=os.getenv('MODELID_CHAT'),
        formatted_system_prompt=static.SYSTEM_PROMPT_GREETING.format(persona=static.PERSONA),
        tool_config=entry_intent_tool_config,
        inference_config=inference_config,
        additional_model_fields=additional_model_fields,
        request_metadata=request_metadata
    )

    # Update state
    content_list = response['output']['message']['content']
    if content_list:  # Check if content list is not empty
        content = content_list[0]
        response_text = content.get('text', content.get('toolUse', {}).get('input', ''))
        transcript.append({'assistant': response_text})
        state['transcript'] = transcript
        messages.append(message)
        state['messages'] = messages
    else:
        logger.warning(f"Empty content received from Bedrock for session {session_id}")
        # Don't append empty messages to avoid Bedrock validation errors

    order_info_found = False  # Flag to track if we found order info

    # execute function tool dynamically
    while stop_reason == "tool_use":
        tool_response = utils.use_tool(messages)
        if tool_response:
            messages.append(tool_response)
            # Check if we got order information from tool response
            try:
                tool_result = json.loads(tool_response['content'][0]['toolResult']['content'][0]['text'])
                if isinstance(tool_result, list):
                    tool_result = tool_result[0]
                if tool_result and isinstance(tool_result, dict) and tool_result.get('id'):
                    state['order_number'] = tool_result.get('id')
                    order_info_found = True
                    state['order_info_found'] = order_info_found
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logging.error(f"Error processing tool response: {e}")

        response, message, stop_reason = utils.process_message(
            messages=messages,
            model_id=os.getenv('MODELID_CHAT'),
            formatted_system_prompt=static.SYSTEM_PROMPT_FETCH_ORDER.format(persona=static.PERSONA, transcript=transcript),
            tool_config=entry_intent_tool_config,
            inference_config=inference_config,
            additional_model_fields=additional_model_fields,
            request_metadata=request_metadata
        )

        content_list = response['output']['message']['content']
        if content_list:  # Check if content list is not empty
            content = content_list[0]
            response_text = content.get('text', content.get('toolUse', {}).get('input', ''))
            transcript.append({'assistant': response_text})
            state['transcript'] = transcript
            messages.append(message)
            state['messages'] = messages
        else:
            logger.warning(f"Empty content received from Bedrock for session {session_id}")
            # Don't append empty messages to avoid Bedrock validation errors

    # Set next_node based on whether we found order information
    if order_info_found:
        state['next_node'] = 'order_confirmation'
    else:
        state['next_node'] = END

    return state
