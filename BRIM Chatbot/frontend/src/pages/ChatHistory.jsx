import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { botService } from '../services/botService';
import { chatService } from '../services/chatService';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { EmptyState } from '../components/EmptyState';
import { LoadingState } from '../components/LoadingState';

const INTENT_BADGES = {
  browsing: { label: 'Browsing', color: '#6366f1', bg: '#eef2ff' },
  buying: { label: 'Buying', color: '#059669', bg: '#ecfdf5' },
  renting: { label: 'Renting', color: '#d97706', bg: '#fffbeb' },
  general_question: { label: 'Question', color: '#0ea5e9', bg: '#f0f9ff' },
  human_assistance: { label: 'Human Help', color: '#dc2626', bg: '#fef2f2' },
};

const STATUS_BADGES = {
  ACTIVE: { label: 'Active', color: '#16a34a', bg: '#dcfce7' },
  ENDED: { label: 'Ended', color: '#6b7280', bg: '#f3f4f6' },
  HANDOFF_REQUESTED: { label: 'Handoff Requested', color: '#dc2626', bg: '#fee2e2' },
  HANDED_OFF: { label: 'Handed Off', color: '#9333ea', bg: '#f3e8ff' },
};

export const ChatHistory = () => {
  const navigate = useNavigate();
  const [conversations, setConversations] = useState([]);
  const [bots, setBots] = useState([]);
  const [selectedBotId, setSelectedBotId] = useState('');
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  const loadData = async () => {
    setLoading(true);
    try {
      const [botList, convList] = await Promise.all([
        botService.getBots().catch(() => []),
        chatService.listAllConversations(selectedBotId ? Number(selectedBotId) : null).catch(() => []),
      ]);
      setBots(botList || []);
      setConversations(convList || []);
    } catch {
      setConversations([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedBotId]);

  const botMap = React.useMemo(() => {
    const map = {};
    bots.forEach((b) => {
      map[b.id] = b.name;
    });
    return map;
  }, [bots]);

  const filteredConversations = conversations.filter((c) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    const botName = botMap[c.bot_id] || '';
    return (
      (c.intent && c.intent.toLowerCase().includes(term)) ||
      (c.status && c.status.toLowerCase().includes(term)) ||
      (c.session_id && c.session_id.toLowerCase().includes(term)) ||
      botName.toLowerCase().includes(term)
    );
  });

  const totalChats = conversations.length;
  const activeChats = conversations.filter((c) => c.status === 'ACTIVE').length;
  const handoffChats = conversations.filter((c) => c.status === 'HANDOFF_REQUESTED').length;

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', paddingBottom: '40px' }}>
      <div className="page-head" style={{ marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, margin: 0 }}>Chat History & Sessions</h1>
          <p className="muted" style={{ margin: '4px 0 0 0', fontSize: '14px' }}>
            Full conversation transcripts, extracted lead intent, and human handoff tracking.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <select
            value={selectedBotId}
            onChange={(e) => setSelectedBotId(e.target.value)}
            style={{
              padding: '8px 12px',
              borderRadius: '8px',
              border: '1px solid #d1d5db',
              fontSize: '14px',
              background: '#fff',
              color: '#374151',
            }}
          >
            <option value="">All Chatbots</option>
            {bots.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
          <input
            className="search"
            placeholder="Filter sessions..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              padding: '8px 12px',
              borderRadius: '8px',
              border: '1px solid #d1d5db',
              fontSize: '14px',
            }}
          />
        </div>
      </div>

      {/* Metrics Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
          marginBottom: '24px',
        }}
      >
        <Card style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '13px', color: '#6b7280', fontWeight: 600 }}>Total Sessions</div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#111827', marginTop: '4px' }}>
            {totalChats}
          </div>
        </Card>
        <Card style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '13px', color: '#16a34a', fontWeight: 600 }}>Active Conversations</div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#16a34a', marginTop: '4px' }}>
            {activeChats}
          </div>
        </Card>
        <Card style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '13px', color: '#dc2626', fontWeight: 600 }}>Handoffs Requested</div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#dc2626', marginTop: '4px' }}>
            {handoffChats}
          </div>
        </Card>
      </div>

      {loading ? (
        <Card style={{ padding: '40px' }}>
          <LoadingState message="Loading conversation records..." />
        </Card>
      ) : filteredConversations.length === 0 ? (
        <Card style={{ padding: '40px' }}>
          <EmptyState
            icon="💬"
            title={searchTerm ? 'No matching conversations' : 'No conversation records yet'}
            description={
              searchTerm
                ? 'Try adjusting your search filters or select a different bot.'
                : 'Start chatting with your bots via the Chat Interface or shareable links to see live sessions here.'
            }
          />
        </Card>
      ) : (
        <Card style={{ padding: '0', overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                  <th style={{ padding: '12px 18px', fontWeight: 600, color: '#4b5563' }}>Session ID</th>
                  <th style={{ padding: '12px 18px', fontWeight: 600, color: '#4b5563' }}>Bot</th>
                  <th style={{ padding: '12px 18px', fontWeight: 600, color: '#4b5563' }}>Intent</th>
                  <th style={{ padding: '12px 18px', fontWeight: 600, color: '#4b5563' }}>Status</th>
                  <th style={{ padding: '12px 18px', fontWeight: 600, color: '#4b5563' }}>Messages</th>
                  <th style={{ padding: '12px 18px', fontWeight: 600, color: '#4b5563' }}>Started At</th>
                  <th style={{ padding: '12px 18px', fontWeight: 600, color: '#4b5563', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredConversations.map((c) => {
                  const intentMeta = INTENT_BADGES[c.intent] || { label: c.intent || 'browsing', color: '#6b7280', bg: '#f3f4f6' };
                  const statusMeta = STATUS_BADGES[c.status] || { label: c.status, color: '#374151', bg: '#f3f4f6' };
                  const botName = botMap[c.bot_id] || `Bot #${c.bot_id}`;
                  const started = c.started_at ? new Date(c.started_at).toLocaleString() : '—';

                  return (
                    <tr
                      key={c.id}
                      style={{
                        borderBottom: '1px solid #f3f4f6',
                        transition: 'background 0.15s ease',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#fcfaff')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      <td style={{ padding: '14px 18px', fontFamily: 'monospace', fontSize: '13px', color: '#4b5563' }}>
                        {c.session_id ? c.session_id.substring(0, 10) + '…' : `#${c.id}`}
                      </td>
                      <td style={{ padding: '14px 18px', fontWeight: 600, color: '#1f2937' }}>
                        {botName}
                      </td>
                      <td style={{ padding: '14px 18px' }}>
                        <span
                          style={{
                            fontSize: '12px',
                            fontWeight: 600,
                            padding: '3px 8px',
                            borderRadius: '999px',
                            color: intentMeta.color,
                            background: intentMeta.bg,
                          }}
                        >
                          {intentMeta.label}
                        </span>
                      </td>
                      <td style={{ padding: '14px 18px' }}>
                        <span
                          style={{
                            fontSize: '12px',
                            fontWeight: 600,
                            padding: '3px 8px',
                            borderRadius: '999px',
                            color: statusMeta.color,
                            background: statusMeta.bg,
                          }}
                        >
                          {statusMeta.label}
                        </span>
                      </td>
                      <td style={{ padding: '14px 18px', color: '#6b7280' }}>
                        {c.message_count || 0} msgs
                      </td>
                      <td style={{ padding: '14px 18px', color: '#6b7280', fontSize: '13px' }}>
                        {started}
                      </td>
                      <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                        <Button
                          variant="secondary"
                          style={{ padding: '6px 12px', fontSize: '13px' }}
                          onClick={() => navigate(`/chat/${c.bot_id}?convo=${c.id}`)}
                        >
                          Open Chat ↗
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
};
