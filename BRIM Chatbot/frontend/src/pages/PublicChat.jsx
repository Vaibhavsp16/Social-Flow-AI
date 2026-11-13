import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { botService } from '../services/botService';
import { chatService } from '../services/chatService';
import { MessageBubble, TypingIndicator } from '../components/ChatMessages';
import { ContactPrompt } from '../components/ContactPrompt';
import { getVisitorId, getTimeContext } from '../utils/visitor';

const formatTime = (dt) => {
  if (!dt) return '';
  const parsed = dt instanceof Date ? dt : new Date(String(dt));
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
};

/**
 * The shareable chatbot page.
 *
 * This is what `/p/{slug}` serves — the public link, the "Open chatbot" button and the embed
 * widget all land here. It is the only chat surface a visitor ever sees, so it has to work without
 * an account, an obvious error when the bot is not published, and a real end state when the backend
 * is unreachable.
 */
export const PublicChat = () => {
  const { slug } = useParams();
  const [searchParams] = useSearchParams();
  const isEmbed = searchParams.get('embed') === '1';
  const visitorId = useRef(getVisitorId());

  const [bot, setBot] = useState(null);
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputVal, setInputVal] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [status, setStatus] = useState('loading'); // loading | ready | error
  const [errorText, setErrorText] = useState('');
  const [contactPrompt, setContactPrompt] = useState(null);
  const [contactBusy, setContactBusy] = useState(false);
  const [contactDone, setContactDone] = useState(false);

  const bodyRef = useRef(null);
  const inputRef = useRef(null);

  // ── Load the bot and open a conversation ──────────────────────────────────
  const start = useCallback(async () => {
    setStatus('loading');
    setErrorText('');
    try {
      const publicBot = await botService.getPublicBot(slug);
      setBot(publicBot);

      const convo = await chatService.createPublicConversation(slug, {
        visitor_id: visitorId.current,
        channel: isEmbed ? 'embed' : 'web',
        ...getTimeContext(),
        language_hint: (navigator.language || 'en').slice(0, 2),
      });
      setConversation(convo);

      const greeting = (convo.messages || []).find((m) => m.sender === 'ASSISTANT');
      setMessages([{
        id: greeting?.id || 'welcome',
        sender: 'bot',
        text:
          greeting?.content ||
          publicBot.greeting_preview ||
          `Hi! I'm ${publicBot.name}. How can I help you today?`,
        time: formatTime(greeting?.timestamp || new Date()),
        sources: [],
      }]);
      setStatus('ready');
      setTimeout(() => inputRef.current?.focus(), 100);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.userMessage;
      setErrorText(
        typeof detail === 'string'
          ? detail
          : 'This chatbot could not be loaded. Please check the link and try again.'
      );
      setStatus('error');
    }
  }, [slug, isEmbed]);

  useEffect(() => {
    start();
  }, [start]);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, isSending, contactPrompt]);

  // ── Idle nudge ────────────────────────────────────────────────────────────
  const idleSeconds = Number(bot?.idle_prompt_seconds ?? 30);

  useEffect(() => {
    if (!conversation?.id || !idleSeconds || contactDone || isSending || contactPrompt) return undefined;
    if (status !== 'ready') return undefined;

    const timer = setTimeout(async () => {
      try {
        const result = await chatService.nudge(conversation.id);
        if (!result?.sent) return;
        setMessages((prev) => [
          ...prev,
          {
            id: `nudge-${Date.now()}`,
            sender: 'bot',
            text: result.reply,
            time: formatTime(new Date()),
            sources: [],
          },
        ]);
        if (result.contact_prompt) setContactPrompt(result.contact_prompt);
      } catch {
        /* ignore: the visitor is not waiting on this */
      }
    }, idleSeconds * 1000);

    return () => clearTimeout(timer);
  }, [conversation?.id, idleSeconds, messages.length, isSending, contactPrompt, contactDone, status]);

  // ── Send ──────────────────────────────────────────────────────────────────
  const send = async (text) => {
    const messageText = (text || inputVal).trim();
    if (!messageText || isSending || !conversation) return;

    setInputVal('');
    setIsSending(true);
    // The contact card is an offer, not a modal: it stays visible while the visitor keeps chatting.
    // Clearing it here hid it for good, because the server only sends the prompt once.
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), sender: 'user', text: messageText, time: formatTime(new Date()), sources: [] },
    ]);

    try {
      const result = await chatService.sendPublicConversationMessage(
        conversation.id,
        messageText
      );
      setMessages((prev) => [
        ...prev,
        {
          id: result.message_id,
          sender: 'bot',
          text: result.reply,
          time: formatTime(new Date()),
          sources: result.sources || [],
          properties: result.properties || [],
          meeting: result.meeting || null,
          isHandoff: result.is_handoff,
        },
      ]);
      if (result.contact_prompt) setContactPrompt(result.contact_prompt);
      if (result.lead?.phone) setContactDone(true);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'bot',
          text:
            err?.userMessage ||
            'Sorry, I could not answer that just now. Please try again in a moment.',
          time: formatTime(new Date()),
          sources: [],
        },
      ]);
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  };

  const submitContact = async (payload) => {
    setContactBusy(true);
    try {
      const result = await chatService.submitContact(conversation.id, payload, false);
      setContactDone(true);
      setContactPrompt(null);
      setMessages((prev) => [
        ...prev,
        {
          id: `contact-${Date.now()}`,
          sender: 'bot',
          text: result.reply || result.message || 'Thank you — the team will be in touch.',
          time: formatTime(new Date()),
          sources: [],
        },
      ]);
    } finally {
      setContactBusy(false);
    }
  };

  const onKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  };

  // ── Layout ────────────────────────────────────────────────────────────────
  const shell = {
    display: 'flex',
    flexDirection: 'column',
    background: '#f7f8fc',
        // Embed mode fills the iframe. `100%` resolved against an auto-height parent and collapsed
        // to the 480px minimum, leaving a band of empty page under the composer.
        height: '100dvh',
        minHeight: 0,
    width: '100%',
  };

  if (status === 'error') {
    return (
      <div style={{ ...shell, alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
        <div style={{ maxWidth: '420px', textAlign: 'center' }}>
          <div style={{ fontSize: '34px', marginBottom: '10px' }}>💬</div>
          <h1 style={{ fontSize: '18px', marginBottom: '8px', color: '#17152a' }}>
            This chatbot is not available
          </h1>
          <p style={{ fontSize: '13.5px', color: '#6b7280', lineHeight: 1.6 }}>{errorText}</p>
          <button
            type="button"
            onClick={start}
            style={{
              marginTop: '16px', padding: '9px 16px', borderRadius: '9px', border: 'none',
              background: '#6d4aff', color: '#fff', fontWeight: 600, cursor: 'pointer',
            }}
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={shell}>
      <style>{`
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-6px); }
        }
        .public-chat-body { flex: 1; overflow-y: auto; padding: ${isEmbed ? '14px' : '20px'}; }
        .public-chat-body::-webkit-scrollbar { width: 5px; }
        .public-chat-body::-webkit-scrollbar-thumb { background: #ddd; border-radius: 4px; }
        .public-quick { display: flex; gap: 6px; flex-wrap: wrap; padding: 8px 16px 0; }
        .public-quick button {
          font-size: 12px; padding: 6px 12px; border-radius: 999px; cursor: pointer;
          border: 1px solid #c4b5fd; background: #f5f3ff; color: #6d4aff;
        }
        .public-quick button:hover { background: #6d4aff; color: #fff; }
      `}</style>

      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: isEmbed ? '12px 14px' : '14px 18px',
          background: '#fff',
          borderBottom: '1px solid #e7e4f3',
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: '38px', height: '38px', borderRadius: '50%',
            background: 'linear-gradient(135deg,#eee9ff,#e5fbff)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px',
          }}
        >
          🤖
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div
            style={{
              fontWeight: 700, fontSize: '15px', color: '#17152a',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            }}
          >
            {bot?.name || 'Assistant'}
          </div>
          <div style={{ fontSize: '11.5px', color: '#6b7280' }}>
            {bot?.company_name ? `${bot.company_name} · ` : ''}Online
          </div>
        </div>
      </header>

      <div className="public-chat-body" ref={bodyRef}>
        {status === 'loading' ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af', fontSize: '13px' }}>
            Opening the chat…
          </div>
        ) : (
          messages.map((msg, index) => <MessageBubble key={msg.id || index} msg={msg} />)
        )}

        {contactPrompt && !contactDone && (
          <ContactPrompt
            text={contactPrompt.text}
            reason={contactPrompt.reason}
            onSubmit={submitContact}
            onDismiss={() => {
              setContactPrompt(null);
              setContactDone(true);
            }}
            busy={contactBusy}
          />
        )}

        {isSending && <TypingIndicator />}
      </div>

      {status === 'ready' && messages.length <= 2 && !isSending && (
        <div className="public-quick">
          {['What do you offer?', 'Tell me more', 'How can I contact you?'].map((label) => (
            <button key={label} type="button" onClick={() => send(label)}>
              {label}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
        style={{
          display: 'flex', gap: '8px', alignItems: 'flex-end',
          padding: '12px 14px', background: '#fff', borderTop: '1px solid #e7e4f3',
          flexShrink: 0,
        }}
      >
        <textarea
          ref={inputRef}
          value={inputVal}
          onChange={(event) => setInputVal(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Type your message…"
          rows={1}
          disabled={status !== 'ready' || isSending}
          style={{
            flex: 1, resize: 'none', border: '1.5px solid #e7e4f3', borderRadius: '12px',
            padding: '10px 14px', fontSize: '14px', lineHeight: 1.5, outline: 'none',
            background: '#fafbff', maxHeight: '110px',
          }}
        />
        <button
          type="submit"
          disabled={!inputVal.trim() || isSending || status !== 'ready'}
          aria-label="Send message"
          style={{
            width: '42px', height: '42px', borderRadius: '50%', border: 'none',
            background: !inputVal.trim() || isSending ? '#e5e7eb' : 'linear-gradient(135deg,#6d4aff,#a54bff)',
            color: !inputVal.trim() || isSending ? '#9ca3af' : '#fff',
            cursor: !inputVal.trim() || isSending ? 'not-allowed' : 'pointer',
            fontSize: '17px', flexShrink: 0,
          }}
        >
          ↑
        </button>
      </form>

      {!isEmbed && (
        <div
          style={{
            textAlign: 'center', fontSize: '10.5px', color: '#9ca3af',
            padding: '6px 0 10px', background: '#fff',
          }}
        >
          Powered by BRIM AI
        </div>
      )}
    </div>
  );
};

export default PublicChat;
