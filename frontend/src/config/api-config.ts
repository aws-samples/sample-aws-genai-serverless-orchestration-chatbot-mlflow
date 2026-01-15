/**
 * Runtime API configuration for WebSocket connections.
 * 
 * This module handles dynamic configuration loading from deployment-time
 * generated config.json and manages WebSocket API endpoint settings.
 */

// Default placeholder values (will be overridden at runtime)
export const API_CONFIG = {
  API_URL: 'placeholder-url',
  REGION: 'us-east-1',
  API_KEY: null // WebSocket API doesn't use API keys
};

// Function to load configuration at runtime
export const loadConfig = async () => {
  try {
    const response = await fetch('/config.json');
    const config = await response.json();
    
    // Update the API_CONFIG with actual values
    API_CONFIG.API_URL = config.API_URL;
    API_CONFIG.REGION = config.REGION;
    
    console.log('Configuration loaded successfully');
    console.log('Using WebSocket API URL:', API_CONFIG.API_URL);
    return true;
  } catch (error) {
    console.error('Failed to load configuration:', error);
    return false;
  }
};

// Initialization function for WebSocket API
export const initializeAPI = () => {
  console.log('WebSocket API configured with:', API_CONFIG);
};

export default initializeAPI;
