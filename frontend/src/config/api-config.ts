/**
 * Runtime API configuration for WebSocket connections.
 *
 * This module handles dynamic configuration loading from deployment-time
 * generated config.json and manages WebSocket API endpoint settings.
 */

// Default values (will be overridden at runtime by config.json)
export const API_CONFIG = {
  API_URL: '',
  REGION: 'us-east-1',
  API_KEY: null // WebSocket API doesn't use API keys
};

// Function to load configuration at runtime
export const loadConfig = async () => {
  try {
    const response = await fetch('/config.json');
    const config = await response.json();

    API_CONFIG.API_URL = config.API_URL;
    API_CONFIG.REGION = config.REGION;

    return true;
  } catch (error) {
    return false;
  }
};
