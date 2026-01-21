"""
Core chatbot application logic and agent memory management.

This module orchestrates the conversation flow using LangGraph workflows,
manages agent state, and integrates with Amazon Bedrock for AI responses.
"""

import json
import os
import time
from datetime import datetime

import boto3
import pytz
from boto3.dynamodb.conditions import Key
from botocore.config import Config
from graphs import primary_graph


# Create PST timezone
pst = pytz.timezone("America/Los_Angeles")

# Get current time in PST
# pst_time = datetime.now(pst)

# Getting env variables
DYNAMO_TABLE = os.getenv("DYNAMO_TABLE")
REGION = os.getenv("AWS_REGION") or os.getenv("APP_REGION")

# Configure the DynamoDB client with timeouts and retries
config = Config(
    connect_timeout=10,  # 10 seconds
    read_timeout=10,  # 10 seconds
    retries={"max_attempts": 3},
    tcp_keepalive=True,
)

# DynamoDB resource - let the SDK use the Gateway endpoint automatically
print(f"Initializing DynamoDB client in region: {REGION}")
ddb_resource = boto3.resource(
    service_name="dynamodb", region_name=REGION, config=config
)

ddb_table = ddb_resource.Table(DYNAMO_TABLE)


def clean_string(input_string):
    """
    Cleans the input string by removing leading and trailing whitespaces.
    """
    return input_string.strip()


def execute_workflow(task, session_dict):
    """
    Executes the workflow based on the task and session_dict.
    """
    session_id = session_dict["session_id"]

    # convert input to message
    clean_task = clean_string(task)

    # Get the latest state
    response = ddb_table.query(
        KeyConditionExpression=Key("conversationId").eq(session_id),
        ScanIndexForward=False,  # Return items in descending order (newest first)
        Limit=1,  # Return only the most recent item
    )

    items = response.get("Items", [])

    # Get the latest message for a conversation
    if len(items) > 0:
        human_message = {"role": "user", "content": [{"text": clean_task}]}

        state_dict = json.loads(items[0]["state"])

        messages = state_dict["messages"]
        if messages[-1]["role"] == "user":
            previous_message = messages[-1]["content"][0]["text"]
            messages[-1]["content"][0]["text"] = (
                previous_message + " " + clean_task
            )
        else:
            messages.append(human_message)

        state_dict["messages"] = messages
        state_dict["transcript"].append({"user": clean_task})
        state_dict["current_turn"] += 1

    else:
        # Create a new state
        state_dict = {}
        state_dict["messages"] = [{"role": "user", "content": [{"text": clean_task}]}]
        state_dict["transcript"] = [{"user": clean_task}]
        state_dict["session_id"] = session_id
        state_dict["session_end"] = False
        state_dict["current_turn"] = 1

    # Check if the session is ended
    if state_dict["session_end"]:
        response_text = (
            "This session has been terminated. Please initiate a new session "
            "for further help"
        )
        state_dict["transcript"].append({"assistant": response_text})
        return {"response": response_text, "metadata": state_dict}

    # write start state to dynamo
    ttl_value = int(time.time()) + (3600 * 4)  # 4 hrs
    item = {
        "conversationId": session_id,
        "state": json.dumps(state_dict),
        "chat_status": state_dict["session_end"],
        "update_ts_pst": str(datetime.now(pst)),
        "ttl": ttl_value,
        "timestamp": int(time.time()),  # Add current timestamp
    }
    ddb_table.put_item(Item=item)

    # Invoke Agentic Graph
    state_dict = primary_graph.graph.invoke(state_dict)

    interation_turn = state_dict["current_turn"]
    # load current state
    response = ddb_table.query(
        KeyConditionExpression=Key("conversationId").eq(session_id),
        ScanIndexForward=False,  # Return items in descending order (newest first)
        Limit=1,  # Return only the most recent item
    )
    items = response.get("Items", [])
    current_state_dict = json.loads(items[0]["state"])
    # confirming previous active run
    current_turn = current_state_dict["current_turn"]

    if interation_turn == current_turn:
        # write state to dynamo
        ttl_value = int(time.time()) + (3600 * 4)  # 4 hrs
        item = {
            "conversationId": session_id,
            "state": json.dumps(state_dict),
            "chat_status": state_dict["session_end"],
            "update_ts_pst": str(datetime.now(pst)),
            "ttl": ttl_value,
            "timestamp": int(time.time()),  # Add current timestamp
        }
        ddb_table.put_item(Item=item)

    # collect response and metadata
    messages = state_dict.get("messages", [])  # Get messages with empty list as default
    if messages:  # Only try to get content if messages exist
        content = messages[-1]["content"][0]
        last_message = content.get("text", content.get("toolUse", {}).get("input", ""))
    else:
        last_message = ""  # Default message if no messages exist

    # return everything except conversational history
    del state_dict["messages"]

    return {"response": last_message, "metadata": state_dict}
