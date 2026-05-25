import React, { useState, useRef, useEffect } from 'react';
import '../styles/AIAssistant.css';
import { useCart } from './cartcontext';
import { componentsData } from '../data/components';
import { useLocation } from 'react-router-dom';

export default function AIAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { sender: 'bot', text: 'Hi! I am your AI PC Builder. Tell me your budget and what you want to do with your PC!' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  
  const { addOrUpdateItem } = useCart();
  const location = useLocation();
  const messagesEndRef = useRef(null);

  const isSupportMode = location.pathname === '/support';

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  useEffect(() => {
    if (isSupportMode && messages.length === 1) {
      setMessages([
        { sender: 'bot', text: 'Hi! I am the AI Support Agent. How can I help you troubleshoot your PC today?' }
      ]);
    }
  }, [isSupportMode]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = { sender: 'user', text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      const endpoint = isSupportMode 
        ? 'http://localhost:5000/api/chat/support'
        : 'http://localhost:5000/api/chat/builder';

      // Send the last few messages for context
      const chatHistory = messages.slice(-5);

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage.text, chatHistory })
      });

      const data = await response.json();

      if (data.error) {
        setMessages(prev => [...prev, { sender: 'bot', text: 'Oops! Error: ' + data.error }]);
      } else {
        setMessages(prev => [...prev, { 
          sender: 'bot', 
          text: data.reply || data.text, 
          build: data.build || null 
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'bot', text: 'Sorry, I am having trouble connecting to the server.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const applyBuildToCart = (buildArray) => {
    buildArray.forEach(itemInfo => {
      const { category, id } = itemInfo;
      if (componentsData[category]) {
        const item = componentsData[category].find(c => c.id === id);
        if (item) {
          addOrUpdateItem(category, item, 1);
        }
      }
    });
    alert("Build applied to cart! Check your PC Builder or Cart to see the parts.");
  };

  return (
    <div className="ai-assistant-container">
      {isOpen && (
        <div className="ai-chat-window">
          <div className="ai-chat-header">
            <h5>{isSupportMode ? 'Support AI' : 'AI PC Builder'}</h5>
            <button className="btn-close btn-close-white" onClick={() => setIsOpen(false)}></button>
          </div>
          <div className="ai-chat-body">
            {messages.map((msg, index) => (
              <div key={index} className={`ai-message ${msg.sender}`}>
                {msg.text}
                {msg.build && msg.build.length > 0 && !isSupportMode && (
                  <button 
                    className="ai-apply-btn"
                    onClick={() => applyBuildToCart(msg.build)}
                  >
                    Apply Parts to Cart
                  </button>
                )}
              </div>
            ))}
            {isTyping && <div className="typing-indicator">AI is thinking...</div>}
            <div ref={messagesEndRef} />
          </div>
          <div className="ai-chat-input">
            <textarea 
              rows="1"
              placeholder="Ask me anything..." 
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                  e.target.style.height = 'auto';
                }
              }}
              style={{
                resize: 'none',
                overflowY: 'auto',
                minHeight: '40px',
                maxHeight: '120px'
              }}
            />
            <button onClick={handleSend}>
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-send-fill" viewBox="0 0 16 16">
                <path d="M15.964.686a.5.5 0 0 0-.65-.65L.767 5.855H.766l-.452.18a.5.5 0 0 0-.082.887l.41.26.001.002 4.995 3.178 3.178 4.995.002.002.26.41a.5.5 0 0 0 .886-.083l6-15Zm-1.833 1.89L6.637 10.07l-.215-.338a.5.5 0 0 0-.154-.154l-.338-.215 7.494-7.494 1.178-.471-.47 1.178Z"/>
              </svg>
            </button>
          </div>
        </div>
      )}

      {!isOpen && (
        <button className="ai-toggle-btn" onClick={() => setIsOpen(true)}>
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" className="bi bi-robot" viewBox="0 0 16 16">
            <path d="M6 12.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5ZM3 8.062C3 6.76 4.235 5.765 5.53 5.889a2.89 2.89 0 0 0 2.583 1.625h2.152a2.89 2.89 0 0 0 2.583-1.625c1.295-.124 2.53.871 2.53 2.173v3.313C15.368 12.673 14.28 14 12.822 14h-8.22C3.14 14 2 12.672 2 11.375V8.062Zm9.263-1.674c-.053-.195-.138-.37-.251-.52-.162-.212-.37-.367-.61-.444A1.89 1.89 0 0 1 10.264 4h-2.91a1.89 1.89 0 0 1-2.14 1.424 1.258 1.258 0 0 0-.61.444c-.113.15-.198.325-.251.52A3.99 3.99 0 0 0 2 8.062v3.313C2 13.228 3.58 15 5.602 15h6.396C14.019 15 15 13.228 15 11.375V8.062a3.99 3.99 0 0 0-2.337-1.674Z"/>
            <path d="M7.05 2A1 1 0 0 1 8 1h1a1 1 0 0 1 1 1v1h-3V2Z"/>
            <path d="M6.5 9.5a.5.5 0 0 1 .5-.5h.01a.5.5 0 0 1 0 1H7a.5.5 0 0 1-.5-.5Zm3 0a.5.5 0 0 1 .5-.5h.01a.5.5 0 0 1 0 1H10a.5.5 0 0 1-.5-.5Z"/>
          </svg>
          Build PC with AI
        </button>
      )}
    </div>
  );
}
