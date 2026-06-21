import React, { useState, useRef, useEffect } from 'react';
import '../styles/AIAssistant.css';
import { useCart } from './cartcontext';
import { componentsData } from '../data/components';
import { useLocation } from 'react-router-dom';
import { createPortal } from 'react-dom';
import { useAuth } from './AuthContext';

export default function AIAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [activeReport, setActiveReport] = useState(null);
  const [messages, setMessages] = useState([
    { sender: 'bot', text: 'Hi! I am your AI PC Builder. Tell me your budget and what you want to do with your PC!' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  
  const { addOrUpdateItem } = useCart();
  const location = useLocation();
  const messagesEndRef = useRef(null);
  const [sessionId, setSessionId] = useState('');
  const { user } = useAuth();

  const isSupportMode = location.pathname === '/support';

  // --- PHASE 3: Conversational Memory (Tied to Account) ---
  useEffect(() => {
    let activeSessionId = '';
    
    // 1. If user is logged in, use their email as the permanent Session ID
    if (user && user.email) {
      activeSessionId = user.email;
    } 
    // 2. If guest, fallback to browser Local Storage
    else {
      let storedId = localStorage.getItem('ai_session_id');
      if (!storedId) {
        storedId = crypto.randomUUID();
        localStorage.setItem('ai_session_id', storedId);
      }
      activeSessionId = storedId;
    }
    
    setSessionId(activeSessionId);

    // Fetch history from MongoDB
    if (!isSupportMode) {
      fetch(`http://localhost:5000/api/chat/history/${activeSessionId}`)
        .then(res => res.json())
        .then(data => {
          if (data.messages && data.messages.length > 0) {
            // Map MongoDB format (role/content/data) to Frontend format
            const formatted = data.messages.map(m => ({
              sender: m.role === 'user' ? 'user' : 'bot',
              text: m.content,
              build: m.build,
              critique: m.critique,
              reviews: m.reviews,
              comparisonData: m.comparisonData
            }));
            // Add the initial greeting, then the history
            setMessages([
              { sender: 'bot', text: 'Hi! I am your AI PC Builder. Tell me your budget and what you want to do with your PC!' },
              ...formatted
            ]);
          } else {
            // Reset to just greeting if no history (e.g. they logged out)
            setMessages([{ sender: 'bot', text: 'Hi! I am your AI PC Builder. Tell me your budget and what you want to do with your PC!' }]);
          }
        })
        .catch(console.error);
    }
  }, [isSupportMode, user]);

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
        body: JSON.stringify({ message: userMessage.text, chatHistory, sessionId })
      });

      const data = await response.json();

      if (data.error) {
        setMessages(prev => [...prev, { sender: 'bot', text: 'Oops! Error: ' + data.error }]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            sender: "bot",
            text: data.reply || data.text,
            build: data.build || null,
            critique: data.critique || null,
            reviews: data.reviews || null,
            comparisonData: data.comparisonData || null,
          },
        ]);
      }
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'bot', text: 'Sorry, I am having trouble connecting to the server.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const applyBuildToCart = (buildArray) => {
    const qtyMap = {};
    buildArray.forEach(item => {
      qtyMap[item.id] = (qtyMap[item.id] || 0) + 1;
    });

    const uniqueIds = new Set();
    buildArray.forEach(itemInfo => {
      const { category, id } = itemInfo;
      if (!uniqueIds.has(id) && componentsData[category]) {
        uniqueIds.add(id);
        const item = componentsData[category].find(c => c.id === id);
        if (item) {
          addOrUpdateItem(category, item, qtyMap[id]);
        }
      }
    });
    alert("Build applied to cart! Check your PC Builder or Cart to see the parts.");
  };

  const handleAddToCart = (msg, index) => {
    applyBuildToCart(msg.build);
    setMessages(prev => {
      const newMsgs = [...prev];
      newMsgs[index] = { ...newMsgs[index], addedToCart: true };
      return newMsgs;
    });
  };

  return (
    <div className="ai-assistant-container">
      {isOpen && (
        <div className="ai-chat-window">
          <div className="ai-chat-header">
            <h5>{isSupportMode ? "Support AI" : "AI PC Builder"}</h5>
            <button
              className="btn-close btn-close-white"
              onClick={() => setIsOpen(false)}
            ></button>
          </div>
          <div className="ai-chat-body">
            {messages.map((msg, index) => (
              <div key={index} className={`ai-message ${msg.sender}`}>
                <p className="mb-2">{msg.text}</p>

                {msg.sender === 'bot' && (msg.build?.length > 0 || msg.comparisonData) && !isSupportMode && (
                  <div className="d-flex flex-column gap-2 mt-3">
                    <button 
                      className="btn btn-outline-dark btn-sm w-100"
                      onClick={() => setActiveReport(msg)}
                      style={{ borderRadius: '4px' }}
                    >
                      📄 View Detailed Report
                    </button>
                    
                    {msg.build && msg.build.length > 0 && (
                      <button 
                        className="btn btn-dark btn-sm w-100"
                        onClick={() => handleAddToCart(msg, index)}
                        disabled={msg.addedToCart}
                        style={{ borderRadius: '4px' }}
                      >
                        {msg.addedToCart ? "Added to Cart" : "Add Build to Cart"}
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
            {isTyping && (
              <div className="typing-indicator">AI is thinking...</div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="ai-chat-input">
            <textarea
              rows="1"
              placeholder="Ask me anything..."
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height =
                  Math.min(e.target.scrollHeight, 120) + "px";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                  e.target.style.height = "auto";
                }
              }}
              style={{
                resize: "none",
                overflowY: "auto",
                minHeight: "40px",
                maxHeight: "120px",
              }}
            />
            <button onClick={handleSend}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                fill="currentColor"
                className="bi bi-send-fill"
                viewBox="0 0 16 16"
              >
                <path d="M15.964.686a.5.5 0 0 0-.65-.65L.767 5.855H.766l-.452.18a.5.5 0 0 0-.082.887l.41.26.001.002 4.995 3.178 3.178 4.995.002.002.26.41a.5.5 0 0 0 .886-.083l6-15Zm-1.833 1.89L6.637 10.07l-.215-.338a.5.5 0 0 0-.154-.154l-.338-.215 7.494-7.494 1.178-.471-.47 1.178Z" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {!isOpen && (
        <button className="ai-toggle-btn" onClick={() => setIsOpen(true)}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            fill="currentColor"
            className="bi bi-robot"
            viewBox="0 0 16 16"
          >
            <path d="M6 12.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5ZM3 8.062C3 6.76 4.235 5.765 5.53 5.889a2.89 2.89 0 0 0 2.583 1.625h2.152a2.89 2.89 0 0 0 2.583-1.625c1.295-.124 2.53.871 2.53 2.173v3.313C15.368 12.673 14.28 14 12.822 14h-8.22C3.14 14 2 12.672 2 11.375V8.062Zm9.263-1.674c-.053-.195-.138-.37-.251-.52-.162-.212-.37-.367-.61-.444A1.89 1.89 0 0 1 10.264 4h-2.91a1.89 1.89 0 0 1-2.14 1.424 1.258 1.258 0 0 0-.61.444c-.113.15-.198.325-.251.52A3.99 3.99 0 0 0 2 8.062v3.313C2 13.228 3.58 15 5.602 15h6.396C14.019 15 15 13.228 15 11.375V8.062a3.99 3.99 0 0 0-2.337-1.674Z" />
            <path d="M7.05 2A1 1 0 0 1 8 1h1a1 1 0 0 1 1 1v1h-3V2Z" />
            <path d="M6.5 9.5a.5.5 0 0 1 .5-.5h.01a.5.5 0 0 1 0 1H7a.5.5 0 0 1-.5-.5Zm3 0a.5.5 0 0 1 .5-.5h.01a.5.5 0 0 1 0 1H10a.5.5 0 0 1-.5-.5Z" />
          </svg>
          Build PC with AI
        </button>
      )}
      )}

      {/* DETAILED REPORT MODAL */}
      {activeReport && createPortal(
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 3000 }}>
          <div style={{ background: '#fff', width: '90%', maxWidth: '800px', maxHeight: '90vh', borderRadius: '8px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div className="d-flex justify-content-between align-items-center p-3 border-bottom bg-light">
              <h5 className="m-0 fw-bold">Detailed AI Report</h5>
              <button className="btn-close" onClick={() => setActiveReport(null)}></button>
            </div>
            
            <div className="p-4" style={{ overflowY: 'auto' }}>
              
              {/* 1. Parts List */}
              {activeReport.build && activeReport.build.length > 0 && (
                <div className="mb-4">
                  <h6 className="fw-bold text-uppercase text-muted border-bottom pb-2">Selected Components</h6>
                  <table className="table table-sm mt-3">
                    <thead className="table-light">
                      <tr>
                        <th>Category</th>
                        <th>Component Name</th>
                        <th>Price</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeReport.build.reduce((acc, curr) => {
                        const existing = acc.find(item => item.id === curr.id);
                        if (existing) {
                          existing.qty = (existing.qty || 1) + 1;
                        } else {
                          acc.push({ ...curr, qty: 1 });
                        }
                        return acc;
                      }, []).map((item, i) => {
                        const fullItem = componentsData[item.category]?.find(c => c.id === item.id);
                        if (!fullItem) return null;
                        const catLabel = item.category.toLowerCase() === 'ram' ? 'RAM' : item.category;
                        return (
                          <tr key={i}>
                            <td className="text-capitalize text-muted">{catLabel}</td>
                            <td className="fw-bold">{fullItem.name} {item.qty > 1 ? <span className="text-danger ms-1">(x{item.qty})</span> : ''}</td>
                            <td>₹{(fullItem.price * item.qty).toLocaleString()}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* 2. Critic Warnings */}
              {activeReport.critique && !activeReport.critique.approved && (
                <div className="alert alert-danger mb-4 border-start border-danger border-4">
                  <h6 className="fw-bold text-danger mb-2">Critic Warnings</h6>
                  <ul className="mb-0">
                    {activeReport.critique.issues.map((issue, i) => <li key={i}>{issue}</li>)}
                  </ul>
                </div>
              )}

              {/* 3. Reviewer Pros/Cons */}
              {activeReport.reviews && activeReport.reviews.length > 0 && (
                <div className="mb-4">
                  <h6 className="fw-bold text-uppercase text-muted border-bottom pb-2">Component Analysis</h6>
                  <div className="row mt-3">
                    {activeReport.reviews.map((r, i) => (
                      <div className="col-md-6 mb-3" key={i}>
                        <div className="card h-100 shadow-sm border-0 bg-light">
                          <div className="card-body p-3">
                            <h6 className="fw-bold mb-1">{r.component}</h6>
                            <span className="badge bg-secondary mb-2">Rating: {r.rating}</span>
                            <div className="text-success" style={{fontSize: '0.9em'}}><strong>Pro:</strong> {r.pros[0]}</div>
                            <div className="text-danger" style={{fontSize: '0.9em'}}><strong>Con:</strong> {r.cons[0]}</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 4. Comparator Data */}
              {activeReport.comparisonData && activeReport.comparisonData.headers && (
                <div className="mb-4">
                  <h6 className="fw-bold text-uppercase text-muted border-bottom pb-2">Comparison Table</h6>
                  <table className="table table-bordered table-striped mt-3">
                    <thead className="table-dark">
                      <tr>
                        {activeReport.comparisonData.headers.map((header, i) => <th key={i}>{header}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {activeReport.comparisonData.rows.map((row, rowIndex) => (
                        <tr key={rowIndex}>
                          {row.map((cell, cellIndex) => (
                            <td key={cellIndex} className={cellIndex === 0 ? "fw-bold text-muted bg-light" : ""}>{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="alert alert-info mt-3 border-0 shadow-sm">
                    <strong>Verdict:</strong> {activeReport.comparisonData.verdict}
                  </div>
                </div>
              )}

            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
