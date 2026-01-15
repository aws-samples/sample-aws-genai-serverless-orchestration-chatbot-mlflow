"""
Order confirmation and validation node.

This module handles order validation, user confirmation requests,
and order status management within the conversation flow.
"""

import logging
import os
import sys
from typing import Any, Dict, List, Optional, Union

import mlflow  # type: ignore
from dotenv import load_dotenv  # type: ignore
from langgraph.graph import END  # type: ignore
from mlflow.entities import SpanType  # type: ignore

from .static import static

# from backend import tools_config
from .tools_config.agent_tool import tool_config as agent_tool_config
from .utils import utils

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
    Process order confirmation node in the conversation flow.

    This node handles:
    1. Order parsing and confirmation status extraction
    2. Tool execution for order verification
    3. Confirmation interaction processing
    4. State management and transcript updates

    Args:
        state (Dict[str, Any]): Current conversation state containing:
            - session_id: Unique session identifier
            - messages: List of conversation messages
            - transcript: Conversation history
            - other state variables

    Returns:
        Dict[str, Any]: Updated state dictionary containing:
            - messages: Updated conversation messages
            - transcript: Updated conversation history
            - order_number: Extracted order number
            - order_confirmed: Boolean indicating confirmation status
            - next_node: Next node in conversation flow ('resolution' or END)
    """
    print('\n <=============== Node: order_confirmation =============> \n')

    session_id = state.get('session_id')
    messages = state.get('messages', [])
    transcript = state.get('transcript', [])

    # Configure API call parameters
    inference_config = {"temperature": static.TEMPERATURE, "maxTokens": static.MAX_TOKENS}
    additional_model_fields = {"top_k": static.TOP_K}
    request_metadata = {'string': 'string'}

    # Set default value
    order_number = None
    is_confirmed = False

    # Skip if last message is already an assistant message to prevent duplicates
    if messages and messages[-1]['role'] == 'assistant':
        # Extract order info from existing assistant message if it has tool use
        last_message = messages[-1]
        if 'content' in last_message:
            for content in last_message['content']:
                if content.get('toolUse') and content['toolUse']['name'] == "get_order_and_confirmation":
                    order_number = content['toolUse']['input']['order_id']
                    is_confirmed = content['toolUse']['input']['is_confirmed']
                    state['order_number'] = order_number
                    state['order_confirmed'] = is_confirmed
                    break
        
        # Update transcript with existing reply
        for content in last_message.get('content', []):
            if 'text' in content:
                reply_text = utils.extract_reply(content['text'])
                if reply_text:
                    transcript.append({'assistant': reply_text})
                    state['transcript'] = transcript
                break
    else:
        # Normal processing when no duplicate assistant message
        response, message, stop_reason = utils.process_message(
            messages=messages,
            model_id=os.getenv('MODELID_CHAT'),
            formatted_system_prompt=static.SYSTEM_PROMPT_PARSE_ORDER.format(persona=static.PERSONA, transcript=transcript),
            tool_config=agent_tool_config,
            inference_config=inference_config,
            additional_model_fields=additional_model_fields,
            request_metadata=request_metadata
        )

        # extracting structured attributes
        for content in response['output']['message']['content']:
            if content.get('toolUse') and content['toolUse']['name'] == "get_order_and_confirmation":
                order_number = content['toolUse']['input']['order_id']
                is_confirmed = content['toolUse']['input']['is_confirmed']
                state['order_number'] = order_number
                state['order_confirmed'] = is_confirmed
                messages.append(message)
                tool_response = utils.use_tool(messages)
                if tool_response:
                    messages.append(tool_response)
                break

        # Add confirmation interaction
        response, message, stop_reason = utils.process_message(
            messages=messages,
            model_id=os.getenv('MODELID_CHAT'),
            formatted_system_prompt=static.SYSTEM_PROMPT_CONFIRM_ORDER.format(persona=static.PERSONA, order_number=order_number),
            tool_config=agent_tool_config,
            inference_config=inference_config,
            additional_model_fields=additional_model_fields,
            request_metadata=request_metadata
        )

        # Update state
        if response and 'output' in response and 'message' in response['output']:
            content_list = response['output']['message']['content']
            if content_list:
                content = content_list[0]
                messages.append(message)
                state['messages'] = messages

                if 'text' in content and stop_reason != "tool_use":
                    reply_text = utils.extract_reply(content['text'])
                    if reply_text:
                        transcript.append({'assistant': reply_text})
                        state['transcript'] = transcript
            else:
                logger.warning(f"Empty content received from Bedrock for session {session_id}")

    state['messages'] = messages
    state['next_node'] = 'resolution' if is_confirmed else END

    return state
