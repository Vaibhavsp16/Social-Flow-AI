import React, { useState } from 'react';

const TIME_SUGGESTIONS = ['Weekday evenings', 'Weekday mornings', 'Afternoon', 'Weekend', 'Anytime'];

/**
 * The contact card the bot offers mid-conversation and after an idle period.
 *
 * Collects a number *and* a time, because a callback list without a time is a list of people who
 * will be called at a bad moment. Both go straight into the leads table.
 */
export const ContactPrompt = ({
  text,
  reason = 'mid_conversation',
  onSubmit,
  onDismiss,
  busy = false,
  accent = '#6d4aff',
}) => {
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [preferredTime, setPreferredTime] = useState('');
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    if (!phone.trim() && !email.trim()) {
      setError('Add a phone number or an email address so we can reach you.');
      return;
    }
    try {
      await onSubmit({
        name: name.trim() || undefined,
        phone: phone.trim() || undefined,
        email: email.trim() || undefined,
        preferred_time: preferredTime.trim() || undefined,
        preferred_contact: phone.trim() ? 'Phone' : 'Email',
        source: reason === 'idle' ? 'idle_prompt' : 'mid_conversation',
        timezone: (() => {
          try {
            return Intl.DateTimeFormat().resolvedOptions().timeZone;
          } catch {
            return undefined;
          }
        })(),
      });
    } catch (err) {
      setError(err?.userMessage || 'Could not save those details. Please try again.');
    }
  };

  return (
    <div
      style={{
        margin: '0 0 16px 42px',
        maxWidth: '78%',
        border: '1px solid #e0d9ff',
        background: '#fbfaff',
        borderRadius: '14px',
        padding: '12px 14px',
        boxShadow: '0 2px 10px rgba(109,74,255,0.07)',
      }}
    >
      <div style={{ fontSize: '13.5px', color: '#17152a', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
        {text}
      </div>

      {!open ? (
        <div style={{ display: 'flex', gap: '8px', marginTop: '10px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setOpen(true)}
            style={{
              padding: '8px 14px', borderRadius: '9px', border: 'none', cursor: 'pointer',
              background: accent, color: '#fff', fontSize: '13px', fontWeight: 600,
            }}
          >
            Share my number
          </button>
          <button
            type="button"
            onClick={onDismiss}
            style={{
              padding: '8px 14px', borderRadius: '9px', cursor: 'pointer',
              background: '#fff', border: '1px solid #e0d9ff', color: '#6b7280', fontSize: '13px',
            }}
          >
            Not now
          </button>
        </div>
      ) : (
        <form onSubmit={submit} style={{ marginTop: '10px', display: 'grid', gap: '8px' }}>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Your name"
            autoComplete="name"
            style={inputStyle}
          />
          <input
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            placeholder="Phone number, e.g. 98250 12345"
            inputMode="tel"
            autoComplete="tel"
            style={inputStyle}
          />
          <input
            value={preferredTime}
            onChange={(event) => setPreferredTime(event.target.value)}
            placeholder="Best time to call — e.g. weekday evenings after 6"
            style={inputStyle}
          />
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {TIME_SUGGESTIONS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setPreferredTime(option)}
                style={{
                  fontSize: '11.5px', padding: '4px 10px', borderRadius: '999px', cursor: 'pointer',
                  border: '1px solid #c4b5fd', background: '#f5f3ff', color: '#6d4aff',
                }}
              >
                {option}
              </button>
            ))}
          </div>
          <input
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="Email (optional)"
            type="email"
            autoComplete="email"
            style={inputStyle}
          />

          {error && <div style={{ fontSize: '12px', color: '#b91c1c' }}>{error}</div>}

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="submit"
              disabled={busy}
              style={{
                padding: '8px 14px', borderRadius: '9px', border: 'none',
                cursor: busy ? 'not-allowed' : 'pointer',
                background: busy ? '#e5e7eb' : accent, color: busy ? '#9ca3af' : '#fff',
                fontSize: '13px', fontWeight: 600,
              }}
            >
              {busy ? 'Saving…' : 'Send'}
            </button>
            <button
              type="button"
              onClick={onDismiss}
              style={{
                padding: '8px 14px', borderRadius: '9px', cursor: 'pointer',
                background: '#fff', border: '1px solid #e0d9ff', color: '#6b7280', fontSize: '13px',
              }}
            >
              Skip
            </button>
          </div>
          <div style={{ fontSize: '11px', color: '#9ca3af' }}>
            Shared only with the company that runs this chat.
          </div>
        </form>
      )}
    </div>
  );
};

const inputStyle = {
  width: '100%',
  padding: '9px 11px',
  borderRadius: '9px',
  border: '1px solid #e0d9ff',
  fontSize: '13px',
  outline: 'none',
  background: '#fff',
  boxSizing: 'border-box',
};

export default ContactPrompt;
