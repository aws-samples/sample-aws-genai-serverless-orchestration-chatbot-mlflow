/**
 * Main chat interface component for real-time conversations.
 * 
 * This component manages WebSocket connections, message handling,
 * and the user interface for the Bedrock chatbot application.
 */

import {
  AppLayout,
  Button,
  Grid,
  Icon,
  Input
} from '@cloudscape-design/components';
import '@cloudscape-design/global-styles/index.css';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { API_CONFIG, loadConfig } from '../config/api-config';

// Interface for chat messages
interface Message {
  role: 'user' | 'assistant' | 'error';
  content: string;
  timestamp: string;
}

// Interface for WebSocket messages
interface WebSocketMessage {
  type: 'status' | 'response' | 'error';
  message?: string;
  response?: string;
  timestamp: string;
  session_id?: string;
  processing_time?: number;
}

// Utility function to extract content from <reply> tags
const extractReplyContent = (text: string): string => {
  const pattern = /<reply>([\s\S]*?)<\/reply>/;
  const match = pattern.exec(text);
  return match ? match[1] : text;
};

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string>('');

  // Initialize WebSocket connection
  const initializeWebSocket = useCallback(() => {
    if (!API_CONFIG.API_URL) {
      const errorMessage: Message = {
        role: 'error',
        content: 'WebSocket API URL not configured',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
      return;
    }

    try {
      console.log('Attempting to connect to WebSocket:', API_CONFIG.API_URL);
      setConnectionStatus('connecting');
      const ws = new WebSocket(API_CONFIG.API_URL);
      websocketRef.current = ws;

      ws.onopen = () => {
        console.log('✅ WebSocket connected successfully');
        setConnectionStatus('connected');
      };

      ws.onmessage = (event) => {
        try {
          const wsMessage: WebSocketMessage = JSON.parse(event.data);
          console.log('WebSocket message received:', wsMessage);
          
          switch (wsMessage.type) {
            case 'status':
              // Handle status messages (e.g., "Processing your request...")
              console.log('Status:', wsMessage.message);
              break;
              
            case 'response':
              // Handle chatbot response
              if (wsMessage.response) {
                const botMessage: Message = {
                  role: 'assistant',
                  content: wsMessage.response,
                  timestamp: wsMessage.timestamp
                };
                setMessages(prev => [...prev, botMessage]);
                setLoading(false);
                
                if (wsMessage.session_id) {
                  sessionIdRef.current = wsMessage.session_id;
                }
              }
              break;
              
            case 'error':
              // Handle error messages as chat messages
              console.error('WebSocket error message:', wsMessage.message);
              const errorMessage: Message = {
                role: 'error',
                content: wsMessage.message || 'An error occurred',
                timestamp: new Date().toISOString()
              };
              setMessages(prev => [...prev, errorMessage]);
              setLoading(false);
              break;
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
          setLoading(false);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionStatus('error');
        setLoading(false);
      };

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setConnectionStatus('disconnected');
        if (event.code !== 1000) { // Not a normal closure
          const errorMessage: Message = {
            role: 'error',
            content: 'Connection lost. Please refresh the page.',
            timestamp: new Date().toISOString()
          };
          setMessages(prev => [...prev, errorMessage]);
        }
        setLoading(false);
      };

    } catch (err) {
      console.error('Error creating WebSocket connection:', err);
      setConnectionStatus('error');
      const errorMessage: Message = {
        role: 'error',
        content: 'Failed to establish WebSocket connection',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    }
  }, []);

  // Initialize configuration and WebSocket
  useEffect(() => {
    const initApp = async () => {
      try {
        const configLoaded = await loadConfig();
        if (configLoaded) {
          console.log('Config loaded, initializing WebSocket...');
          initializeWebSocket();
        } else {
          const errorMessage: Message = {
            role: 'error',
            content: 'Failed to load API configuration',
            timestamp: new Date().toISOString()
          };
          setMessages(prev => [...prev, errorMessage]);
        }
      } catch (err) {
        console.error('Error initializing app:', err);
        const errorMessage: Message = {
          role: 'error',
          content: 'Failed to initialize application',
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, errorMessage]);
      }
    };
    
    initApp();

    // Cleanup WebSocket on component unmount
    return () => {
      if (websocketRef.current) {
        websocketRef.current.close(1000, 'Component unmounting');
      }
    };
  }, [initializeWebSocket]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleInputChange = (event: { detail: { value: string } }) => {
    setInput(event.detail.value);
  };

  const handleKeyDown = (event: any) => {
    if (event.detail.key === 'Enter') {
      handleSendMessage();
    }
  };

  const handleClear = () => {
    setMessages([]);
    setInput('');
    // Create a new session ID when clearing
    sessionIdRef.current = `session-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    console.log('Clear chat: New session ID created:', sessionIdRef.current);
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return '';
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim() || loading || connectionStatus !== 'connected') {
      return;
    }

    setLoading(true);

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    };

    try {
      setMessages(prev => [...prev, userMessage]);
      const messageText = input;
      setInput('');

      // Create a session ID if one doesn't exist
      if (!sessionIdRef.current) {
        sessionIdRef.current = `session-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      }
      
      // Create the WebSocket message
      const wsMessage = {
        action: 'sendMessage',
        input: messageText,
        session_id: sessionIdRef.current
      };
      
      console.log('Sending WebSocket message:', wsMessage);
      
      // Send message via WebSocket
      if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
        websocketRef.current.send(JSON.stringify(wsMessage));
      } else {
        throw new Error('WebSocket connection is not open');
      }
      
    } catch (error: any) {
      console.error('Error sending message:', error);
      const errorMessage: Message = {
        role: 'error',
        content: typeof error === 'object' ? error.message : 'Failed to send message',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
      setLoading(false);
    }
  };

  // Function to render code blocks with syntax highlighting
  const formatMessageContent = (content: string) => {
    // First extract any code blocks
    const formattedContent = extractReplyContent(content);
    
    // Simple regex to identify code blocks with ```
    const codeBlockRegex = /```([\s\S]*?)```/g;
    
    // Split the content by code blocks
    const parts = formattedContent.split(codeBlockRegex);
    
    if (parts.length === 1) {
      // No code blocks, return the text as is
      return <span>{formattedContent}</span>;
    }
    
    // Render text and code blocks alternately
    return parts.map((part, index) => {
      // Even indices are regular text, odd indices are code
      if (index % 2 === 0) {
        return <span key={index}>{part}</span>;
      } else {
        return (
          <div 
            key={index} 
            className="code-block"
          >
            <button 
              className="copy-button"
              onClick={() => {
                navigator.clipboard.writeText(part);
              }}
            >
              {/* eslint-disable react/jsx-no-literals */}
              Copy
              {/* eslint-enable react/jsx-no-literals */}
            </button>
            <pre>{part}</pre>
          </div>
        );
      }
    });
  };

  return (
    <AppLayout
      content={
        <div style={{
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          position: 'relative'
        }}>
          {/* Banner Section - Fixed at top */}
          <div style={{ 
            flexShrink: 0,
            height: '30px',
            padding: '16px 24px',
            borderBottom: '2px solid #eaeded',
            backgroundColor: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
          </div>

          {/* Clear Chat Button - Fixed under banner */}
          <div style={{ 
            flexShrink: 0,
            height: '45px',
            padding: '8px 24px',
            borderBottom: '1px solid #f0f0f0',
            backgroundColor: '#ffffff',
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center'
          }}>
            <Button
              onClick={handleClear}
              disabled={loading || messages.length === 0}
              iconName="remove"
            >
              {/* eslint-disable react/jsx-no-literals */}
              Clear Chat
              {/* eslint-enable react/jsx-no-literals */}
            </Button>
          </div>

          <div 
            style={{ 
              flex: 1,
              minHeight: 0,
              padding: '16px 24px',
              display: 'flex',
              flexDirection: 'column'
            }}
            ref={chatContainerRef}
          >
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                border: '1px solid #eaeded',
                borderRadius: '8px',
                padding: '16px',
                backgroundColor: '#f8f8f8'
              }}
            >
              {connectionStatus === 'connecting' ? (
                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '100%',
                  color: '#5f6b7a',
                  padding: '20px'
                }}>
                  <div style={{
                    width: '40px',
                    height: '40px',
                    border: '4px solid #f3f3f3',
                    borderTop: '4px solid #0073bb',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite'
                  }}></div>
                  {/* eslint-disable react/jsx-no-literals */}
                  <p style={{ marginTop: '15px' }}>Establishing connection...</p>
                  {/* eslint-enable react/jsx-no-literals */}
                  <style>{`
                    @keyframes spin {
                      0% { transform: rotate(0deg); }
                      100% { transform: rotate(360deg); }
                    }
                  `}</style>
                </div>
              ) : messages.length === 0 ? (
                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '100%',
                  color: '#5f6b7a',
                  padding: '20px'
                }}>
                  <Icon name="status-info" size="big" />
                  {/* eslint-disable react/jsx-no-literals */}
                  <p style={{ marginTop: '10px' }}>Start a conversation with AWS Bedrock</p>
                  {/* eslint-enable react/jsx-no-literals */}
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {messages.map((msg, index) => {
                    const isFirstMessageOfType = index === 0 || messages[index - 1].role !== msg.role;
                    const isConsecutiveMessage = index > 0 && messages[index - 1].role === msg.role;
                    
                    return (
                      <div
                        key={index}
                        className="message-animation"
                        style={{ 
                          marginBottom: isConsecutiveMessage ? '2px' : '8px',
                          marginTop: isConsecutiveMessage && msg.role === 'assistant' ? '2px' : '0'
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                            alignItems: 'flex-end'
                          }}
                        >
                          {isFirstMessageOfType && msg.role === 'assistant' && (
                            <div style={{ 
                              width: '28px', 
                              height: '28px', 
                              borderRadius: '50%', 
                              backgroundColor: '#232f3e',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              marginRight: '8px',
                              flexShrink: 0,
                              marginBottom: '2px'
                            }}>
                              {/* eslint-disable react/jsx-no-literals */}
                              <span style={{ color: 'white', fontWeight: 'bold', fontSize: '12px' }}>AI</span>
                              {/* eslint-enable react/jsx-no-literals */}
                            </div>
                          )}
                          
                          {!isFirstMessageOfType && msg.role === 'assistant' && (
                            <div style={{ width: '28px', marginRight: '8px' }}></div>
                          )}
                          
                          <div
                            style={{
                              maxWidth: '85%',
                              backgroundColor: msg.role === 'user' ? '#0073bb' : msg.role === 'error' ? '#ffeaea' : '#ffffff',
                              color: msg.role === 'user' ? 'white' : msg.role === 'error' ? '#d13212' : '#16191f',
                              borderRadius: msg.role === 'user' 
                                ? (isConsecutiveMessage ? '18px 4px 18px 18px' : '18px 18px 4px 18px')
                                : (isConsecutiveMessage ? '4px 18px 18px 18px' : '18px 18px 18px 4px'),
                              padding: '10px 14px',
                              boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
                              border: msg.role === 'assistant' ? '1px solid #eaeded' : msg.role === 'error' ? '1px solid #f5b7a5' : 'none',
                            }}
                          >
                            <div style={{ 
                              whiteSpace: 'pre-wrap',
                              lineHeight: '1.5',
                              fontSize: '15px'
                            }}>
                              {formatMessageContent(msg.content)}
                            </div>
                            
                            <div style={{
                              fontSize: '11px',
                              color: msg.role === 'user' ? 'rgba(255,255,255,0.7)' : '#5f6b7a',
                              marginTop: '6px',
                              textAlign: 'right'
                            }}>
                              {formatTimestamp(msg.timestamp)}
                            </div>
                          </div>
                          
                          {isFirstMessageOfType && msg.role === 'user' && (
                            <div style={{ 
                              width: '28px', 
                              height: '28px', 
                              borderRadius: '50%', 
                              backgroundColor: '#f2f3f3',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              marginLeft: '8px',
                              border: '1px solid #d1d5db',
                              flexShrink: 0,
                              marginBottom: '2px'
                            }}>
                              <Icon name="user-profile" size="normal" />
                            </div>
                          )}
                          
                          {!isFirstMessageOfType && msg.role === 'user' && (
                            <div style={{ width: '28px', marginLeft: '8px' }}></div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          <div style={{ 
            flexShrink: 0,
            height: '100px',
            padding: '24px',
            borderTop: '2px solid #eaeded',
            backgroundColor: '#ffffff'
          }}>
            <Grid
              gridDefinition={[{ colspan: 10 }, { colspan: 2 }]}
            >
              <div style={{ position: 'relative' }}>
                <Input
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  /* eslint-disable react/jsx-no-literals */
                  placeholder={connectionStatus === 'connected' ? "Type your message..." : "Connecting..."}
                  /* eslint-enable react/jsx-no-literals */
                  disabled={loading || connectionStatus !== 'connected'}
                  autoFocus
                  spellcheck={true}
                />
              </div>
              <Button
                onClick={handleSendMessage}
                loading={loading}
                variant="primary"
                iconName="send"
                fullWidth
              >
                {/* eslint-disable react/jsx-no-literals */}
                Send
                {/* eslint-enable react/jsx-no-literals */}
              </Button>
            </Grid>
          </div>
        </div>
      }
      navigationHide={true}
      toolsHide={true}
      contentType="default"
      disableContentPaddings={true}
    />
  );
};

export default Chat;
