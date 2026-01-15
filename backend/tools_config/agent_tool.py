tool_config = {
    "toolChoice": {"auto": {}},
    "tools": [
        {
            "toolSpec": {
                "name": "get_order_and_confirmation",
                "description": "Extract order number and confirmation status from conversation transcript",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "The extracted order number without special characters"
                            },
                            "is_confirmed": {
                                "type": "boolean",
                                "description": "Whether the user confirmed the order (True) or not (False)"
                            }
                        },
                        "required": ["order_id", "is_confirmed"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "cancel_order",
                "description": "Cancels an order based on a provided order_id. Only orders that are 'processing' can be cancelled",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "The order_id pertaining to a particular order"
                            }
                        },
                        "required": ["order_id"]
                    }
                }
            },
        },
        {
            "toolSpec": {
                "name": "update_order",
                "description": "Update an order based on a provided order_id. Only orders that are 'processing' can be cancelled",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "The order_id pertaining to a particular order"
                            }
                        },
                        "required": ["order_id"]
                    }
                }
            }
        }
    ],
}