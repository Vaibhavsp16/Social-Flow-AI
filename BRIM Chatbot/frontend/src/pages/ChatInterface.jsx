import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { botService } from '../services/botService';
import { chatService } from '../services/chatService';
import { Button } from '../components/Button';

// ── Helpers ───────────────────────────────────────────────────────────────────

const INTENT_LABELS = {
  browsing: { label: 'Browsing', color: '#6366f1', bg: '#eef2ff' },
  buying: { label: 'Buying', color: '#059669', bg: '#ecfdf5' },
  renting: { label: 'Renting', color: '#d97706', bg: '#fffbeb' },
  general_question: { label: 'Question', color: '#0ea5e9', bg: '#f0f9ff' },
  human_assistance: { label: 'Human Help', color: '#dc2626', bg: '#fef2f2' },
};

const HANDOFF_PHRASES = ['speak to a human', 'talk to a person', 'real person', 'human advisor'];

function IntentBadge({ intent }) {
  const meta = INTENT_LABELS[intent] || { label: intent, color: '#6f7184', bg: '#f3f4f6' };
  return (
    <span style={{
      fontSize: '10.5px', fontWeight: 700, padding: '2px 8px',
      borderRadius: '999px', background: meta.bg, color: meta.color,
      border: `1px solid ${meta.color}22`, letterSpacing: '0.3px',
    }}>
      {meta.label}
    </span>
  );
}

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '16px' }}>
      <div style={{
        width: '32px', height: '32px', borderRadius: '50%',
        background: 'linear-gradient(135deg,#eee9ff,#e5fbff)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '16px', flexShrink: 0,
      }}>🤖</div>
      <div style={{
        background: '#fff', border: '1px solid #e7e4f3', borderRadius: '0 14px 14px 14px',
        padding: '12px 16px', display: 'flex', gap: '5px', alignItems: 'center',
        boxShadow: '0 2px 8px rgba(109,74,255,0.06)',
      }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: '7px', height: '7px', borderRadius: '50%',
            background: '#a78bfa',
            animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
          }} />
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ msg }) {
  const isUser = msg.sender === 'user';
  const isSystem = msg.sender === 'system';

  if (isSystem) {
    return (
      <div style={{ textAlign: 'center', margin: '10px 0' }}>
        <span style={{
          fontSize: '11.5px', color: '#9ca3af', background: '#f9fafb',
          border: '1px solid #e5e7eb', borderRadius: '999px', padding: '4px 12px',
        }}>{msg.text}</span>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-end',
      gap: '10px', marginBottom: '16px',
      flexDirection: isUser ? 'row-reverse' : 'row',
    }}>
      {!isUser && (
        <div style={{
          width: '32px', height: '32px', borderRadius: '50%', flexShrink: 0,
          background: 'linear-gradient(135deg,#eee9ff,#e5fbff)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '16px',
        }}>🤖</div>
      )}

      <div style={{ maxWidth: '78%', display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start' }}>
        <div style={{
          padding: '11px 15px',
          borderRadius: isUser ? '14px 14px 0 14px' : '0 14px 14px 14px',
          background: isUser
            ? 'linear-gradient(135deg,#6d4aff,#a54bff)'
            : (msg.isHandoff ? '#fef2f2' : '#fff'),
          color: isUser ? '#fff' : (msg.isHandoff ? '#dc2626' : '#17152a'),
          border: isUser ? 'none' : `1px solid ${msg.isHandoff ? '#fecaca' : '#e7e4f3'}`,
          boxShadow: isUser
            ? '0 4px 14px rgba(109,74,255,0.25)'
            : '0 2px 8px rgba(109,74,255,0.06)',
          fontSize: '14px', lineHeight: '1.55', whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}>
          {msg.text}
        </div>

        {/* Source citations */}
        {msg.sources && msg.sources.length > 0 && (
          <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
            {msg.sources.map((src, i) => (
              <span key={i}
                title={src.snippet}
                style={{
                  fontSize: '10.5px', padding: '2px 8px',
                  background: '#eff6ff', color: '#1d4ed8',
                  border: '1px solid #bfdbfe', borderRadius: '999px',
                  display: 'inline-flex', alignItems: 'center', gap: '4px',
                }}>
                📄 {src.source_name}
                <span style={{
                  fontSize: '9px', background: '#dbeafe',
                  padding: '1px 4px', borderRadius: '3px',
                }}>
                  {Math.round(src.similarity_score * 100)}%
                </span>
              </span>
            ))}
          </div>
        )}

        <span style={{ fontSize: '10px', color: '#9ca3af', marginTop: '4px' }}>
          {msg.time}
        </span>
      </div>
    </div>
  );
}

// ── State Summary Panel ────────────────────────────────────────────────────────
function StateSummary({ state, intent }) {
  if (!state || Object.keys(state).filter(k => k !== 'intent').length === 0) return null;
  const entries = [];
  if (state.location) entries.push({ icon: '📍', label: 'Location', value: state.location });
  if (state.bhk) entries.push({ icon: '🏠', label: 'BHK', value: `${state.bhk} BHK` });
  if (state.budget_max) {
    const b = state.budget_max;
    const display = b >= 10_000_000 ? `₹${(b / 10_000_000).toFixed(1)} Cr` : `₹${(b / 100_000).toFixed(0)} L`;
    entries.push({ icon: '💰', label: 'Budget', value: display });
  }
  if (state.amenities?.length) entries.push({ icon: '✨', label: 'Amenities', value: state.amenities.join(', ') });

  if (!entries.length) return null;

  return (
    <div style={{
      padding: '10px 14px', background: '#f0edff',
      borderBottom: '1px solid #e0d9ff', fontSize: '12px',
    }}>
      <div style={{ color: '#6d4aff', fontWeight: 700, marginBottom: '5px', fontSize: '11px' }}>
        📋 CHAT CONTEXT
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
        {entries.map((e, i) => (
          <span key={i} style={{
            background: '#fff', border: '1px solid #c4b5fd',
            borderRadius: '6px', padding: '2px 8px', color: '#5b21b6',
          }}>
            {e.icon} <b>{e.label}:</b> {e.value}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Main ChatInterface ─────────────────────────────────────────────────────────
export const ChatInterface = () => {
  const { id: botId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const chatBodyRef = useRef(null);
  const inputRef = useRef(null);

  const [bot, setBot] = useState(null);
  const [conversation, setConversation] = useState(null);
  const [conversationList, setConversationList] = useState([]);
  const [messages, setMessages] = useState([]);
  const [inputVal, setInputVal] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [intent, setIntent] = useState('browsing');
  const [conversationState, setConversationState] = useState({});
  const [showHistory, setShowHistory] = useState(false);
  const [isHandedOff, setIsHandedOff] = useState(false);

  // Quick-action suggestions by intent
  const quickActions = {
    browsing: ['Tell me about your properties', 'Show me available options', 'What areas do you cover?'],
    buying: ['What is the price?', 'Is it ready to move in?', 'What are the payment plans?'],
    renting: ['What is the monthly rent?', 'Is it furnished?', 'How long is the lease?'],
    general_question: ['I have a question', 'Tell me more', 'Can you explain?'],
    human_assistance: [],
  };

  const formatTime = (dt) => {
    if (!dt) return '';
    return new Date(dt).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  // ── Load bot info ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!botId) return;
    botService.getBot(botId)
      .then(data => setBot(data))
      .catch(() => {});
  }, [botId]);

  // ── Start or restore a conversation ───────────────────────────────────────
  const startNewConversation = useCallback(async () => {
    if (!botId) return;
    setIsLoading(true);
    setError(null);
    try {
      const convo = await chatService.createConversation(botId);
      setConversation(convo);
      setMessages([{
        id: 'welcome',
        sender: 'bot',
        text: bot?.welcome_message || `Hi there! 👋 I'm ${bot?.name || 'your AI assistant'}. How can I help you today?`,
        time: formatTime(new Date()),
        sources: [],
      }]);
      setIntent('browsing');
      setConversationState({});
      setIsHandedOff(false);
    } catch (err) {
      setError(err.userMessage || 'Could not start a conversation. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [botId, bot]);

  const loadConversation = useCallback(async (convoId) => {
    setIsLoading(true);
    try {
      const convo = await chatService.getConversation(convoId);
      setConversation(convo);
      setIntent(convo.intent || 'browsing');
      try { setConversationState(JSON.parse(convo.conversation_state || '{}')); } catch { setConversationState({}); }

      const mapped = convo.messages.map(m => ({
        id: m.id,
        sender: m.sender === 'USER' ? 'user' : 'bot',
        text: m.content,
        time: formatTime(m.timestamp),
        sources: (() => { try { return JSON.parse(m.metadata_json || '{}').sources || []; } catch { return []; } })(),
        isHandoff: (() => { try { return JSON.parse(m.metadata_json || '{}').is_handoff || false; } catch { return false; } })(),
      }));

      const welcome = {
        id: 'welcome', sender: 'bot',
        text: bot?.welcome_message || `Hi there! 👋 I'm ${bot?.name || 'your AI assistant'}. How can I help?`,
        time: '', sources: [],
      };
      setMessages(mapped.length > 0 ? mapped : [welcome]);
      setIsHandedOff(convo.status === 'HANDOFF_REQUESTED' || convo.status === 'HANDED_OFF');
      setShowHistory(false);
    } catch {
      startNewConversation();
    } finally {
      setIsLoading(false);
    }
  }, [bot, startNewConversation]);

  // Initialise exactly once per bot. Depending on `bot` here previously re-ran this effect
  // when the bot finished loading, silently creating a second empty conversation on every open.
  const initialisedBotRef = useRef(null);

  useEffect(() => {
    if (!botId || initialisedBotRef.current === botId) return;
    initialisedBotRef.current = botId;
    const existingId = searchParams.get('convo');
    if (existingId) {
      loadConversation(existingId);
    } else {
      startNewConversation();
    }
  }, [botId, bot, searchParams, loadConversation, startNewConversation]);

  // Once the bot details arrive, refresh the placeholder welcome bubble if the user has not
  // sent anything yet, so the real welcome message shows without opening another conversation.
  useEffect(() => {
    if (!bot) return;
    setMessages((prev) => {
      if (prev.length !== 1 || prev[0].id !== 'welcome') return prev;
      return [
        {
          ...prev[0],
          text: bot.welcome_message || `Hi there! 👋 I'm ${bot.name || 'your AI assistant'}. How can I help you today?`,
        },
      ];
    });
  }, [bot]);

  // ── Load conversation history list ─────────────────────────────────────────
  const loadHistory = async () => {
    if (!botId) return;
    try {
      const list = await chatService.listConversations(botId, 20);
      setConversationList(list);
    } catch {}
    setShowHistory(true);
  };

  // ── Auto-scroll ────────────────────────────────────────────────────────────
  useEffect(() => {
    chatBodyRef.current?.scrollTo({ top: chatBodyRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, isSending]);

  // ── Send message ───────────────────────────────────────────────────────────
  const handleSend = async (text) => {
    const messageText = (text || inputVal).trim();
    if (!messageText || isSending || !conversation) return;

    setInputVal('');
    setIsSending(true);

    const userMsg = {
      id: Date.now(),
      sender: 'user',
      text: messageText,
      time: formatTime(new Date()),
      sources: [],
    };
    setMessages(prev => [...prev, userMsg]);

    try {
      const result = await chatService.sendConversationMessage(conversation.id, messageText);

      setIntent(result.intent || 'browsing');
      setConversationState(result.conversation_state || {});
      setIsHandedOff(result.is_handoff);

      setMessages(prev => [...prev, {
        id: result.message_id,
        sender: 'bot',
        text: result.reply,
        time: formatTime(new Date()),
        sources: result.sources || [],
        confidence: result.confidence,
        isHandoff: result.is_handoff,
      }]);

      if (result.is_handoff) {
        setMessages(prev => [...prev, {
          id: 'handoff-notice',
          sender: 'system',
          text: '🔔 Handoff requested — a human advisor will be in touch soon.',
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        sender: 'bot',
        text: err.userMessage || 'Sorry, something went wrong. Please try again.',
        time: formatTime(new Date()),
        sources: [], isError: true,
      }]);
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      <style>{`
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-6px); }
        }
        .chat-interface-wrap { display: flex; height: calc(100vh - 66px); background: #f7f8fc; }
        .chat-history-panel {
          width: 280px; background: #fff; border-right: 1px solid #e7e4f3;
          display: flex; flex-direction: column; overflow: hidden;
        }
        .chat-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
        .chat-messages { flex: 1; overflow-y: auto; padding: 20px; }
        .chat-messages::-webkit-scrollbar { width: 5px; }
        .chat-messages::-webkit-scrollbar-thumb { background: #ddd; border-radius: 4px; }
        .chat-input-bar {
          padding: 14px 16px; background: #fff;
          border-top: 1px solid #e7e4f3; display: flex; gap: 10px; align-items: flex-end;
        }
        .chat-textarea {
          flex: 1; border: 1.5px solid #e7e4f3; border-radius: 12px;
          padding: 10px 14px; resize: none; outline: none; font-size: 14px;
          line-height: 1.5; max-height: 120px; background: #fafbff;
          transition: border-color 0.2s;
        }
        .chat-textarea:focus { border-color: #6d4aff; background: #fff; }
        .quick-actions { display: flex; gap: 6px; flex-wrap: wrap; padding: 8px 16px 0; }
        .quick-pill {
          font-size: 12px; padding: 5px 12px; border-radius: 999px; cursor: pointer;
          border: 1px solid #c4b5fd; background: #f5f3ff; color: #6d4aff;
          transition: all 0.15s; white-space: nowrap;
        }
        .quick-pill:hover { background: #6d4aff; color: #fff; border-color: #6d4aff; }
        .history-item {
          padding: 10px 14px; cursor: pointer; border-bottom: 1px solid #f3f4f6;
          font-size: 13px; transition: background 0.15s;
        }
        .history-item:hover { background: #f5f3ff; }
        .history-item.active { background: #ede9fe; }
        @media (max-width: 700px) {
          .chat-history-panel { display: none; }
        }
      `}</style>

      <div className="chat-interface-wrap">

        {/* ── Conversation History Sidebar ─────────────────────────────── */}
        <div className="chat-history-panel">
          <div style={{ padding: '14px', borderBottom: '1px solid #e7e4f3' }}>
            <div style={{ fontWeight: 700, fontSize: '13px', marginBottom: '8px' }}>Conversations</div>
            <button
              onClick={startNewConversation}
              style={{
                width: '100%', padding: '8px 12px', borderRadius: '8px',
                background: 'linear-gradient(135deg,#6d4aff,#a54bff)', color: '#fff',
                border: 'none', fontWeight: 600, fontSize: '13px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center',
              }}
            >
              ＋ New Chat
            </button>
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            {!showHistory ? (
              <div
                style={{ padding: '12px 14px', cursor: 'pointer', color: '#6d4aff', fontSize: '13px', fontWeight: 600 }}
                onClick={loadHistory}
              >
                📋 View chat history
              </div>
            ) : conversationList.length === 0 ? (
              <div style={{ padding: '20px 14px', color: '#9ca3af', fontSize: '13px', textAlign: 'center' }}>
                No previous chats yet.
              </div>
            ) : (
              conversationList.map(c => (
                <div
                  key={c.id}
                  className={`history-item ${conversation?.id === c.id ? 'active' : ''}`}
                  onClick={() => loadConversation(c.id)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 600 }}>
                      {c.intent ? INTENT_LABELS[c.intent]?.label || c.intent : 'Chat'}
                    </span>
                    <span style={{
                      fontSize: '10px', padding: '2px 6px', borderRadius: '999px',
                      background: c.status === 'ACTIVE' ? '#ecfdf5' : '#f3f4f6',
                      color: c.status === 'ACTIVE' ? '#059669' : '#6b7280',
                    }}>{c.status}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
                    {new Date(c.started_at).toLocaleDateString()} · {c.message_count} msgs
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* ── Main Chat Area ─────────────────────────────────────────── */}
        <div className="chat-main">

          {/* Chat Header */}
          <div style={{
            padding: '12px 20px', background: '#fff',
            borderBottom: '1px solid #e7e4f3',
            display: 'flex', alignItems: 'center', gap: '12px',
          }}>
            <button
              onClick={() => navigate(`/bots/${botId}`)}
              style={{
                border: 'none', background: 'none', cursor: 'pointer',
                fontSize: '18px', color: '#6f7184', padding: '4px',
              }}
              title="Back to bot"
            >←</button>

            <div style={{
              width: '40px', height: '40px', borderRadius: '50%', flexShrink: 0,
              background: 'linear-gradient(135deg,#eee9ff,#e5fbff)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px',
            }}>🤖</div>

            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: '15px' }}>
                {bot?.name || 'AI Assistant'}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
                <span style={{ fontSize: '12px', color: '#6b7280' }}>Online · {bot?.language || 'English'}</span>
                <IntentBadge intent={intent} />
              </div>
            </div>

            <button
              onClick={() => { setShowHistory(true); loadHistory(); }}
              style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#6d4aff', fontSize: '13px', fontWeight: 600 }}
            >
              History
            </button>
          </div>

          {/* State Context Bar */}
          <StateSummary state={conversationState} intent={intent} />

          {/* Messages */}
          <div className="chat-messages" ref={chatBodyRef}>
            {isLoading ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
                <div style={{ fontSize: '28px', marginBottom: '10px' }}>💬</div>
                <div>Starting your conversation...</div>
              </div>
            ) : error ? (
              <div style={{
                textAlign: 'center', padding: '40px', color: '#dc2626',
                background: '#fef2f2', borderRadius: '12px', margin: '20px',
              }}>
                <div style={{ fontSize: '28px', marginBottom: '10px' }}>⚠️</div>
                <div>{error}</div>
                <button
                  onClick={startNewConversation}
                  style={{ marginTop: '12px', padding: '8px 16px', background: '#dc2626', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer' }}
                >
                  Try Again
                </button>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <MessageBubble key={msg.id || idx} msg={msg} />
              ))
            )}
            {isSending && <TypingIndicator />}
          </div>

          {/* Quick-action suggestion pills */}
          {!isSending && !isHandedOff && messages.length <= 2 && (
            <div className="quick-actions">
              {(quickActions[intent] || quickActions.browsing).map((action, i) => (
                <div key={i} className="quick-pill" onClick={() => handleSend(action)}>
                  {action}
                </div>
              ))}
            </div>
          )}

          {/* Input bar */}
          {isHandedOff ? (
            <div style={{
              padding: '16px', background: '#fef2f2', borderTop: '1px solid #fecaca',
              display: 'flex', alignItems: 'center', gap: '10px',
            }}>
              <span style={{ fontSize: '20px' }}>🤝</span>
              <div style={{ fontSize: '14px', color: '#dc2626' }}>
                <b>Handoff requested.</b> A human advisor will be in touch shortly.
              </div>
              <button
                onClick={startNewConversation}
                style={{
                  marginLeft: 'auto', padding: '8px 14px', borderRadius: '8px',
                  background: '#fff', border: '1px solid #fca5a5', color: '#dc2626',
                  cursor: 'pointer', fontSize: '13px', fontWeight: 600,
                }}
              >
                New Chat
              </button>
            </div>
          ) : (
            <div className="chat-input-bar">
              <textarea
                ref={inputRef}
                className="chat-textarea"
                placeholder="Type your message… (Enter to send)"
                value={inputVal}
                onChange={e => {
                  setInputVal(e.target.value);
                  e.target.style.height = 'auto';
                  e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
                }}
                onKeyDown={handleKeyDown}
                disabled={isSending || isLoading}
                rows={1}
              />
              <button
                onClick={() => handleSend()}
                disabled={isSending || !inputVal.trim() || isLoading}
                style={{
                  width: '44px', height: '44px', borderRadius: '50%', border: 'none',
                  background: !inputVal.trim() || isSending
                    ? '#e5e7eb'
                    : 'linear-gradient(135deg,#6d4aff,#a54bff)',
                  color: !inputVal.trim() || isSending ? '#9ca3af' : '#fff',
                  cursor: !inputVal.trim() || isSending ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '18px', transition: 'all 0.2s', flexShrink: 0,
                  boxShadow: inputVal.trim() ? '0 4px 12px rgba(109,74,255,0.3)' : 'none',
                }}
                title="Send message"
              >
                {isSending ? '⏳' : '↑'}
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
};
