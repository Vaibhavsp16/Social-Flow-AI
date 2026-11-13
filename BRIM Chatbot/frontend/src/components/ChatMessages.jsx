import React from 'react';

/**
 * Transcript rendering shared by the authenticated chat and the public chatbot page.
 *
 * Kept in one place because the two surfaces must look identical: a citation pill or a property card
 * that renders on one and not the other looks like a bug to whoever is being shown the demo.
 */

export function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '16px' }}>
      <div
        style={{
          width: '32px', height: '32px', borderRadius: '50%',
          background: 'linear-gradient(135deg,#eee9ff,#e5fbff)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '16px', flexShrink: 0,
        }}
      >
        🤖
      </div>
      <div
        style={{
          background: '#fff', border: '1px solid #e7e4f3', borderRadius: '0 14px 14px 14px',
          padding: '12px 16px', display: 'flex', gap: '5px', alignItems: 'center',
          boxShadow: '0 2px 8px rgba(109,74,255,0.06)',
        }}
      >
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            style={{
              width: '7px', height: '7px', borderRadius: '50%',
              background: '#a78bfa',
              animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

function MeetingNote({ meeting }) {
  if (!meeting) return null;
  const label = {
    visit: 'Site visit',
    video: 'Video call',
    office: 'Office meeting',
    call: 'Call',
  }[meeting.mode] || 'Call';
  return (
    <div
      style={{
        marginTop: '8px', background: '#ecfdf5', border: '1px solid #a7f3d0',
        borderRadius: '10px', padding: '8px 12px', fontSize: '12.5px', color: '#065f46',
        display: 'flex', gap: '8px', alignItems: 'center',
      }}
    >
      <span>📅</span>
      <span>
        <b>{label} requested</b>
        {meeting.preferred_slot ? ` — ${meeting.preferred_slot}` : ''}
        <span style={{ opacity: 0.75 }}> · the team will confirm</span>
      </span>
    </div>
  );
}

export function MessageBubble({ msg }) {
  const isUser = msg.sender === 'user';
  const isSystem = msg.sender === 'system';

  if (isSystem) {
    return (
      <div style={{ textAlign: 'center', margin: '10px 0' }}>
        <span
          style={{
            fontSize: '11.5px', color: '#9ca3af', background: '#f9fafb',
            border: '1px solid #e5e7eb', borderRadius: '999px', padding: '4px 12px',
          }}
        >
          {msg.text}
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex', alignItems: 'flex-end',
        gap: '10px', marginBottom: '16px',
        flexDirection: isUser ? 'row-reverse' : 'row',
      }}
    >
      {!isUser && (
        <div
          style={{
            width: '32px', height: '32px', borderRadius: '50%', flexShrink: 0,
            background: 'linear-gradient(135deg,#eee9ff,#e5fbff)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '16px',
          }}
        >
          🤖
        </div>
      )}

      <div
        style={{
          maxWidth: '78%', display: 'flex', flexDirection: 'column',
          alignItems: isUser ? 'flex-end' : 'flex-start',
        }}
      >
        <div
          style={{
            padding: '11px 15px',
            borderRadius: isUser ? '14px 14px 0 14px' : '0 14px 14px 14px',
            background: isUser
              ? 'linear-gradient(135deg,#6d4aff,#a54bff)'
              : msg.isHandoff ? '#fef2f2' : '#fff',
            color: isUser ? '#fff' : msg.isHandoff ? '#dc2626' : '#17152a',
            border: isUser ? 'none' : `1px solid ${msg.isHandoff ? '#fecaca' : '#e7e4f3'}`,
            boxShadow: isUser
              ? '0 4px 14px rgba(109,74,255,0.25)'
              : '0 2px 8px rgba(109,74,255,0.06)',
            fontSize: '14px', lineHeight: '1.55', whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {msg.text}
        </div>

        {msg.properties && msg.properties.length > 0 && (
          <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
            {msg.properties.map((property) => (
              <div
                key={property.property_id}
                style={{
                  background: '#fff', border: '1px solid #e7e4f3',
                  borderLeft: '3px solid #6d4aff', borderRadius: '10px',
                  padding: '10px 12px', minWidth: '260px',
                  boxShadow: '0 2px 8px rgba(109,74,255,0.06)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px' }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', color: '#17152a' }}>
                    {property.title}
                  </div>
                  <div style={{ fontWeight: 700, fontSize: '13px', color: '#6d4aff', whiteSpace: 'nowrap' }}>
                    {property.price_display}
                  </div>
                </div>
                <div style={{ fontSize: '11.5px', color: '#6b7280', marginTop: '2px' }}>
                  {[
                    property.bhk ? `${property.bhk} BHK` : null,
                    property.property_type,
                    property.location,
                  ].filter(Boolean).join(' · ')}
                </div>
                {property.amenities?.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '6px' }}>
                    {property.amenities.slice(0, 5).map((amenity) => (
                      <span
                        key={amenity}
                        style={{
                          fontSize: '10px', padding: '1px 7px', borderRadius: '999px',
                          background: '#f5f3ff', color: '#6d4aff', border: '1px solid #e0d9ff',
                        }}
                      >
                        {amenity}
                      </span>
                    ))}
                  </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                  <span style={{ fontSize: '9.5px', color: property.is_mock ? '#b45309' : '#059669', fontWeight: 600 }}>
                    {property.is_mock ? 'DEVELOPMENT DATA' : property.status}
                  </span>
                  {property.brochure_url && (
                    <a
                      href={property.brochure_url}
                      target="_blank"
                      rel="noreferrer"
                      style={{ fontSize: '11px', color: '#1d4ed8', textDecoration: 'none', fontWeight: 600 }}
                    >
                      Brochure ↗
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        <MeetingNote meeting={msg.meeting} />

        {msg.sources && msg.sources.length > 0 && (
          <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
            {msg.sources.map((src, i) => (
              <span
                key={i}
                title={src.snippet}
                style={{
                  fontSize: '10.5px', padding: '2px 8px',
                  background: '#eff6ff', color: '#1d4ed8',
                  border: '1px solid #bfdbfe', borderRadius: '999px',
                  display: 'inline-flex', alignItems: 'center', gap: '4px',
                }}
              >
                📄 {src.source_name}
                <span style={{ fontSize: '9px', background: '#dbeafe', padding: '1px 4px', borderRadius: '3px' }}>
                  {Math.round((src.similarity_score || 0) * 100)}%
                </span>
              </span>
            ))}
          </div>
        )}

        {msg.time && (
          <span style={{ fontSize: '10px', color: '#9ca3af', marginTop: '4px' }}>{msg.time}</span>
        )}
      </div>
    </div>
  );
}
