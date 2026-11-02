import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { StatCard } from '../components/StatCard';
import { useToast } from '../context/ToastContext';
import { analyticsService, rangeParams } from '../services/analyticsService';

const INTENT_COLORS = {
  buying: '#6d4aff',
  renting: '#1f9d8b',
  browsing: '#f0a132',
  other: '#9aa0b4',
};

function IntentBars({ intents, total }) {
  const rows = ['buying', 'renting', 'browsing', 'other'].map((key) => ({
    key,
    value: intents?.[key] || 0,
    pct: total ? Math.round(((intents?.[key] || 0) / total) * 100) : 0,
  }));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {rows.map((row) => (
        <div key={row.key}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '4px' }}>
            <span style={{ textTransform: 'capitalize' }}>{row.key}</span>
            <span className="muted">{row.value} · {row.pct}%</span>
          </div>
          <div style={{ height: '8px', background: '#f1eff8', borderRadius: '999px', overflow: 'hidden' }}>
            <div style={{ width: `${row.pct}%`, height: '100%', background: INTENT_COLORS[row.key] }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function VolumeChart({ volume }) {
  const max = Math.max(1, ...volume.map((day) => day.conversations));
  const shown = volume.slice(-30);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: '4px', height: '120px' }}>
      {shown.map((day) => (
        <div
          key={day.date}
          title={`${day.date}: ${day.conversations} conversations, ${day.messages} messages`}
          style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%' }}
        >
          <div
            style={{
              height: `${Math.max(4, (day.conversations / max) * 100)}%`,
              background: '#6d4aff',
              borderRadius: '3px 3px 0 0',
              minWidth: '4px',
            }}
          />
        </div>
      ))}
    </div>
  );
}

export const Analytics = () => {
  const { showToast } = useToast();
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const params = useMemo(() => rangeParams(days), [days]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    analyticsService
      .overview(params)
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch(() => {
        if (!cancelled) setData(null);
        showToast?.('Could not load analytics.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [params, showToast]);

  const totals = data?.totals || {};
  const hasData = Boolean(data?.has_data);

  const exportCsv = async (kind) => {
    setExporting(true);
    try {
      await analyticsService.downloadCsv(kind, params);
      showToast?.(`${kind} CSV downloaded.`);
    } catch {
      showToast?.('Export failed.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Reporting & Analytics</h1>
          <p className="muted">Computed from your own conversations, messages, leads and knowledge sources.</p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <select
            className="search"
            style={{ width: '150px' }}
            value={days}
            onChange={(event) => setDays(Number(event.target.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <Button variant="secondary" disabled={exporting} onClick={() => exportCsv('conversations')}>
            Conversations CSV
          </Button>
          <Button variant="secondary" disabled={exporting} onClick={() => exportCsv('leads')}>
            Leads CSV
          </Button>
          <Button variant="secondary" disabled={exporting} onClick={() => exportCsv('unanswered')}>
            Unanswered CSV
          </Button>
        </div>
      </div>

      <p className="muted" style={{ fontSize: '12.5px', marginTop: '-6px' }}>
        {params.start} → {params.end}
        {' · '}Unique users are distinct conversation sessions; resolved means the conversation produced a lead or
        ended without a handoff.
      </p>

      <div className="grid metric-grid">
        <StatCard label="Total conversations" value={totals.conversations ?? 0} />
        <StatCard label="Unique users" value={totals.unique_users ?? 0} />
        <StatCard label="Messages" value={totals.messages ?? 0} />
        <StatCard label="Leads" value={totals.leads ?? 0} />
        <StatCard label="Handoffs" value={totals.handoffs ?? 0} />
        <StatCard
          label="Resolution rate"
          value={hasData ? `${totals.resolution_rate ?? 0}%` : '—'}
        />
      </div>

      {!loading && !hasData && (
        <Card style={{ marginTop: '24px', textAlign: 'center', padding: '48px 20px' }}>
          <h2 style={{ fontSize: '18px', marginBottom: '8px' }}>No conversation data yet.</h2>
          <p className="muted" style={{ maxWidth: '520px', margin: '0 auto' }}>
            Analytics appear here as soon as visitors talk to one of your bots. Nothing is estimated or
            back-filled.
          </p>
        </Card>
      )}

      {hasData && (
        <>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px', marginTop: '24px' }}>
            <Card>
              <h2 style={{ fontSize: '16px', marginBottom: '14px' }}>Intent distribution</h2>
              <IntentBars intents={data.intents} total={totals.conversations} />
            </Card>
            <Card>
              <h2 style={{ fontSize: '16px', marginBottom: '14px' }}>Conversation volume</h2>
              <VolumeChart volume={data.volume || []} />
              <p className="muted" style={{ fontSize: '12px', marginTop: '10px' }}>
                Daily conversations, last {Math.min(30, (data.volume || []).length)} active days.
                {' '}Avg {totals.avg_messages_per_conversation ?? 0} messages per conversation.
              </p>
            </Card>
          </div>

          <Card style={{ marginTop: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h2 style={{ fontSize: '16px' }}>Bot usage</h2>
              <Button variant="secondary" disabled={exporting} onClick={() => exportCsv('bot_usage')}>
                Export
              </Button>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: '#6f7184' }}>
                    <th style={{ padding: '8px 10px' }}>Bot</th>
                    <th style={{ padding: '8px 10px' }}>Conversations</th>
                    <th style={{ padding: '8px 10px' }}>Messages</th>
                    <th style={{ padding: '8px 10px' }}>Leads</th>
                    <th style={{ padding: '8px 10px' }}>Handoffs</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.per_bot || []).map((bot) => (
                    <tr key={bot.bot_id} style={{ borderTop: '1px solid #f0eef7' }}>
                      <td style={{ padding: '8px 10px' }}>
                        <Link to={`/bots/${bot.bot_id}`} style={{ color: '#6d4aff', fontWeight: 600 }}>
                          {bot.bot_name}
                        </Link>
                      </td>
                      <td style={{ padding: '8px 10px' }}>{bot.conversations}</td>
                      <td style={{ padding: '8px 10px' }}>{bot.messages}</td>
                      <td style={{ padding: '8px 10px' }}>{bot.leads}</td>
                      <td style={{ padding: '8px 10px' }}>{bot.handoffs}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card style={{ marginTop: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h2 style={{ fontSize: '16px' }}>Unanswered questions ({data.unanswered?.length || 0})</h2>
              <Button variant="secondary" disabled={exporting} onClick={() => exportCsv('unanswered')}>
                Export
              </Button>
            </div>
            {(data.unanswered || []).length === 0 ? (
              <p className="muted" style={{ fontSize: '13px' }}>No refused or unanswered questions in this range.</p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '13px', lineHeight: 1.7 }}>
                {data.unanswered.slice(0, 10).map((row, index) => (
                  <li key={`${row.conversation_id}-${index}`}>
                    {row.question}
                    <span className="muted"> — #{row.conversation_id}, {row.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  );
};
