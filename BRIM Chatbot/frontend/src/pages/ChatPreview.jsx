import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { botService } from '../services/botService';
import { chatService } from '../services/chatService';
import { Button } from '../components/Button';

export const ChatPreview = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const chatBottomRef = useRef(null);

  const [bot, setBot] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputVal, setInputVal] = useState('');
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    const load = async () => {
      if (id) {
        try {
          const data = await botService.getBot(id);
          setBot(data);
          setMessages([
            {
              sender: 'bot',
              text: data.welcome_message || `Hi! 👋 I'm ${data.name}. How can I help you today?`,
              sources: [],
            },
          ]);
        } catch {
          setMessages([
            {
              sender: 'bot',
              text: 'Hi! 👋 How can I help you today?',
              sources: [],
            },
          ]);
        }
      } else {
        setMessages([
          {
            sender: 'bot',
            text: 'Hi! 👋 I am your AI assistant. How can I help you today?',
            sources: [],
          },
        ]);
      }
    };
    load();
  }, [id]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSending]);

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!inputVal.trim() || isSending) return;

    const userText = inputVal.trim();
    setInputVal('');

    const newMessages = [...messages, { sender: 'user', text: userText }];
    setMessages(newMessages);
    setIsSending(true);

    // Format conversation history for API
    const history = newMessages.slice(1, -1).map((m) => ({
      role: m.sender === 'user' ? 'user' : 'assistant',
      content: m.text,
    }));

    try {
      if (id) {
        const response = await chatService.sendMessage(id, userText, history);
        setMessages((prev) => [
          ...prev,
          {
            sender: 'bot',
            text: response.reply,
            sources: response.sources || [],
            confidence: response.confidence,
          },
        ]);
      } else {
        // Generic fallback when no bot id provided
        setMessages((prev) => [
          ...prev,
          {
            sender: 'bot',
            text: 'This is a demo preview without a connected knowledge base. Please select a specific bot to test semantic retrieval.',
            sources: [],
          },
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: `Error retrieving response: ${err.userMessage || 'Please try again.'}`,
          sources: [],
          isError: true,
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="logo">
          BRIM<span>AI</span>
        </div>
        <Button variant="secondary" onClick={() => (id ? navigate(`/bots/${id}`) : navigate('/dashboard'))}>
          ← Back to Workspace
        </Button>
      </header>

      <main className="main" style={{ maxWidth: '880px', padding: '24px 20px' }}>
        <div className="page-head" style={{ marginBottom: '16px' }}>
          <div>
            <h1>AI Knowledge & Semantic QA Preview</h1>
            <p className="muted">
              Live grounded chat testing bot-level vector retrieval, source citations, and hallucination refusal.
            </p>
          </div>
        </div>

        <div className="chat-demo" style={{ boxShadow: '0 8px 30px rgba(0,0,0,0.06)', borderRadius: '16px' }}>
          <div className="chat-head" style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
            <div className="bot-icon" style={{ width: '38px', height: '38px', fontSize: '14px' }}>
              🤖
            </div>
            <div>
              <b style={{ fontSize: '15px' }}>{bot?.name || 'BRIM Assistant'}</b>
              <div style={{ fontSize: '11.5px', color: 'var(--success)', marginTop: '2px' }}>
                ● {bot?.status || 'Online'} · {bot?.language || 'English'} · Grounded RAG Enabled
              </div>
            </div>
          </div>

          <div className="chat-body" style={{ minHeight: '380px', maxHeight: '520px', overflowY: 'auto', padding: '20px' }}>
            {messages.map((m, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: m.sender === 'bot' ? 'flex-start' : 'flex-end',
                  marginBottom: '14px',
                }}
              >
                <div
                  className={`bubble ${m.sender === 'bot' ? 'bot-b' : 'user-b'}`}
                  style={{
                    maxWidth: '85%',
                    lineHeight: '1.5',
                    fontSize: '14px',
                    whiteSpace: 'pre-wrap',
                    backgroundColor: m.isError ? '#fee2e2' : undefined,
                    color: m.isError ? '#991b1b' : undefined,
                    border: m.isError ? '1px solid #f87171' : undefined,
                  }}
                >
                  {m.text}
                </div>

                {/* Grounded Source Citations */}
                {m.sources && m.sources.length > 0 && (
                  <div style={{ marginTop: '6px', maxWidth: '85%' }}>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
                      📚 RETRIEVED SOURCES ({m.sources.length}):
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {m.sources.map((src, sIdx) => (
                        <span
                          key={sIdx}
                          title={`Score: ${Math.round(src.similarity_score * 100)}% | ${src.snippet}`}
                          style={{
                            fontSize: '11px',
                            padding: '3px 8px',
                            background: '#eff6ff',
                            color: '#1d4ed8',
                            border: '1px solid #bfdbfe',
                            borderRadius: '12px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          📄 {src.source_name}
                          {src.page_number && <span style={{ opacity: 0.75 }}>({src.page_number})</span>}
                          <span style={{ fontSize: '9.5px', background: '#dbeafe', padding: '1px 4px', borderRadius: '4px' }}>
                            {Math.round(src.similarity_score * 100)}%
                          </span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {isSending && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', color: 'var(--text-muted)', fontSize: '13px' }}>
                <span className="animate-spin" style={{ display: 'inline-block' }}>⚙️</span> Retrieving grounded knowledge...
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          <form className="chat-input" onSubmit={handleSend} style={{ padding: '14px 16px', borderTop: '1px solid var(--border)' }}>
            <input
              placeholder="Ask a question about this business or knowledge base..."
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              disabled={isSending}
              style={{ flex: 1, padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border)' }}
            />
            <Button type="submit" variant="primary" disabled={isSending || !inputVal.trim()}>
              {isSending ? 'Searching...' : 'Send'}
            </Button>
          </form>
        </div>
      </main>
    </div>
  );
};
