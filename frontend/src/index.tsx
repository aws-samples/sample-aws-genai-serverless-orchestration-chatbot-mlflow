import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import '@cloudscape-design/global-styles/index.css';

// Add global styles for full-page layout
const style = document.createElement('style');
style.textContent = `
  html, body, #root {
    height: 100%;
    margin: 0;
    padding: 0;
    overflow: hidden;
  }
  
  .App {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  /* Fix for AppLayout to take full height */
  [class*="awsui_root"] {
    height: 100%;
  }
  
  [class*="awsui_content-wrapper"] {
    height: 100%;
  }
  
  /* Custom scrollbar for chat */
  ::-webkit-scrollbar {
    width: 8px;
  }
  
  ::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 10px;
  }
  
  ::-webkit-scrollbar-thumb {
    background: #c4c4c4;
    border-radius: 10px;
  }
  
  ::-webkit-scrollbar-thumb:hover {
    background: #a0a0a0;
  }
  
  /* Animation for new messages */
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  
  .message-animation {
    animation: fadeIn 0.3s ease-out forwards;
  }
  
  /* Code block styling */
  .code-block {
    background-color: #f1f3f4;
    border-radius: 4px;
    padding: 12px;
    font-family: 'Courier New', monospace;
    overflow-x: auto;
    margin: 8px 0;
    border: 1px solid #dfe1e5;
    position: relative;
  }
  
  .code-block pre {
    margin: 0;
    white-space: pre-wrap;
  }
  
  .copy-button {
    position: absolute;
    top: 5px;
    right: 5px;
    cursor: pointer;
    background-color: #e1e3e5;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 12px;
    border: none;
    transition: background-color 0.2s;
  }
  
  .copy-button:hover {
    background-color: #d1d3d5;
  }
`;
document.head.appendChild(style);

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
