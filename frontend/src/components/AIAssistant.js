import React, { useState, useRef, useEffect } from 'react';
import '../styles/AIAssistant.css';
import { useCart } from './cartcontext';
import { componentsData } from '../data/components';
import { useLocation } from 'react-router-dom';
import { createPortal } from 'react-dom';
import { useAuth } from './AuthContext';

const API = 'http://localhost:5000';
const MAX_MESSAGE = 500;

function errorText(data) {
  return 'Sorry, something went wrong: ' + ((data && (data.error || data.message)) || 'unknown error');
}

const rupees = (n) => (n == null ? 'unknown' : '₹' + Math.round(n).toLocaleString('en-IN'));

function verdictText(verdict) {
  if (!verdict) return 'Could not verify compatibility.';
  if (verdict.status === 'compatible') {
    return verdict.unknowns && verdict.unknowns.length
      ? `No problems found by code (could not check: ${verdict.unknowns.join(', ')}).`
      : 'Compatible: all rules passed (checked by code).';
  }
  if (verdict.status === 'incompatible') return 'Not compatible: ' + (verdict.problems || []).join(' | ');
  return 'Could not verify compatibility.';
}

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
  // One agent thread per chat session: a RANDOM id, not the email. Approving and claiming a
  // build needs the thread id, so it must not be guessable (and emails stay out of the agent DB).
  const [threadId] = useState(() => {
    try {
      let id = localStorage.getItem('agent_thread_id');
      if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem('agent_thread_id', id);
      }
      return id;
    } catch {
      return crypto.randomUUID();
    }
  });

  // --- Chat history: logged-in users by email, guests by a browser id ---
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
      if (!isSupportMode) {
        // The Python agent (through Express). A valid build comes back PAUSED,
        // waiting for the user's Approve/Reject; it is never added to the cart by itself.
        const response = await fetch(`${API}/api/agent/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: userMessage.text, threadId })
        });
        const data = await response.json();
        setMessages(prev => [...prev, {
          sender: 'bot',
          text: data.reply || errorText(data),
          approval: data.status === 'awaiting_approval' ? data.approval : null,
          threadId: data.thread_id || threadId,
          comparisonData: data.comparison && data.comparison.rows && data.comparison.rows.length
            ? data.comparison : null,
        }]);
        return;
      }

      // Send the last few messages for context
      const chatHistory = messages.slice(-5);

      const response = await fetch(`${API}/api/chat/support`, {
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

  const updateMessage = (index, changes) => {
    setMessages(prev => prev.map((m, i) => (i === index ? { ...m, ...changes } : m)));
  };

  // Approve -> the server records the approval for THIS exact build (its hash) ->
  // the server cart route re-checks it and returns the parts -> only then do they enter the cart.
  const handleDecision = async (index, approved) => {
    const msg = messages[index];
    const body = { threadId: msg.threadId, buildHash: msg.approval.build_hash };
    updateMessage(index, { approvalBusy: true, approvalError: null });
    try {
      const res = await fetch(`${API}/api/agent/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...body, approved })
      });
      const decision = await res.json();
      if (!approved) {
        updateMessage(index, { approvalBusy: false, approvalState: 'rejected', approvalNote: decision.reply });
        return;
      }
      if (decision.status !== 'approved') {
        updateMessage(index, { approvalBusy: false, approvalError: decision.reply || errorText(decision) });
        return;
      }
      const cartRes = await fetch(`${API}/api/cart/add-build`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const cart = await cartRes.json();
      if (!cartRes.ok || cart.status !== 'added') {
        updateMessage(index, { approvalBusy: false, approvalError: cart.message || errorText(cart) });
        return;
      }
      cart.items.forEach(item => {
        addOrUpdateItem(item.category, { id: item.id, name: item.name, price: item.price, category: item.category }, 1);
      });
      updateMessage(index, { approvalBusy: false, approvalState: 'added' });
    } catch (err) {
      updateMessage(index, { approvalBusy: false, approvalError: 'Could not reach the server. Nothing was added.' });
    }
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
                <p className="mb-2" style={{ whiteSpace: 'pre-line' }}>{msg.text}</p>

                {msg.sender === 'bot' && (msg.build?.length > 0 || msg.comparisonData) && !isSupportMode && (
                  <div className="d-flex flex-column gap-2 mt-3">
                    <button
                      className="btn btn-outline-dark btn-sm w-100"
                      onClick={() => setActiveReport(msg)}
                      style={{ borderRadius: '4px' }}
                    >
                      📄 View Detailed Report
                    </button>
                  </div>
                )}

                {/* Nothing reaches the cart until the user approves THIS build */}
                {msg.sender === 'bot' && msg.approval && !isSupportMode && (() => {
                  const a = msg.approval;
                  // Approval is disabled for a FAIL or could_not_verify verdict.
                  const canApprove = a.can_approve === true && a.verdict && a.verdict.status === 'compatible';
                  const decided = msg.approvalState === 'added' || msg.approvalState === 'rejected';
                  return (
                    <div className="mt-3 p-2 border rounded bg-white text-dark" style={{ fontSize: '0.85em' }}>
                      <div className="fw-bold mb-1">Approve this build?</div>
                      <table className="table table-sm mb-2">
                        <tbody>
                          {a.cards.map(card => (
                            <tr key={card.id}>
                              <td className="text-muted">{card.label}</td>
                              <td>{card.name}</td>
                              <td className="text-end text-nowrap">{rupees(card.price)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <div className="fw-bold">Total: {rupees(a.total)} (calculated by code)</div>
                      <div className={canApprove ? 'text-success' : 'text-danger'}>Verdict: {verdictText(a.verdict)}</div>
                      {!decided && (
                        <div className="d-flex gap-2 mt-2">
                          <button className="btn btn-dark btn-sm flex-fill" disabled={!canApprove || msg.approvalBusy}
                                  onClick={() => handleDecision(index, true)}>
                            {msg.approvalBusy ? 'Checking…' : 'Approve & add to cart'}
                          </button>
                          <button className="btn btn-outline-secondary btn-sm flex-fill" disabled={msg.approvalBusy}
                                  onClick={() => handleDecision(index, false)}>
                            Reject
                          </button>
                        </div>
                      )}
                      {!canApprove && !decided && <div className="text-danger mt-1">This build can't be approved: it is not verified as compatible.</div>}
                      {msg.approvalState === 'added' && <div className="text-success mt-2">Approved and added to your cart.</div>}
                      {msg.approvalState === 'rejected' && <div className="text-muted mt-2">{msg.approvalNote || 'Rejected. Nothing was added.'}</div>}
                      {msg.approvalError && <div className="text-danger mt-2">{msg.approvalError}</div>}
                    </div>
                  );
                })()}
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
              maxLength={MAX_MESSAGE}
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
                  {activeReport.comparisonData.verdict && (
                    <div className="alert alert-info mt-3 border-0 shadow-sm">
                      <strong>Verdict:</strong> {activeReport.comparisonData.verdict}
                    </div>
                  )}
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
