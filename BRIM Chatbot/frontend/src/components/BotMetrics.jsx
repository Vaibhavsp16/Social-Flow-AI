import React, { useEffect, useMemo, useState } from 'react';
import { Button } from './Button';
import { Card } from './Card';
import { StatCard } from './StatCard';
import { useToast } from '../context/ToastContext';
import { analyticsService, rangeParams } from '../services/analyticsService';

/**
 * Real bot metrics. Every number comes from /analytics/bots/{id}; when the window holds no
 * conversations the component says so instead of rendering zeros as if they were performance.
 */
function LiveStat({ label, value }) {
  return (
    <span style={{ display: 'flex', alignItems: 'baseline', gap: '6px', fontSize: '13px' }}>
      <b style={{ fontSize: '15px' }}>{value ?? 0}</b>
      <span className="muted" style={{ fontSize: '12px' }}>
        {label}
      </span>
    </span>
  );
}

export const BotMetrics = ({ botId, compact = false }) => {
  const { showToast } = useToast();
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [live, setLive] = useState(null);

  const params = useMemo(() => rangeParams(days), [days]);

  // Counters refresh on their own so the numbers move while someone is talking to the bot, which is
  // the whole point of an analytics screen during a demo. The full report stays on its own cadence
  // because it is expensive; this endpoint is a handful of counts.
  useEffect(() => {
    if (!botId) return undefined;
    let cancelled = false;

    const pull = () => {
      analyticsService
        .botLive(botId)
        .then((payload) => {
          if (!cancelled) setLive(payload);
        })
        .catch(() => {
          if (!cancelled) setLive(null);
        });
    };

    pull();
    const timer = setInterval(pull, 10000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [botId]);

  useEffect(() => {
    if (!botId) return undefined;
    let cancelled = false;
    setLoading(true);
    analyticsService
      .bot(botId, params)
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [botId, params]);

  const totals = data?.totals || {};
  const hasData = Boolean(data?.has_data);

  const exportCsv = async (kind) => {
    try {
      await analyticsService.downloadCsv(kind, { ...params, bot_id: botId });
      showToast?.(`${kind} CSV downloaded.`);
    } catch {
      showToast?.('Export failed.');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '16px' }}>Performance</h3>
          <p className="muted" style={{ fontSize: '12px', margin: '2px 0 0' }}>
            {params.start} → {params.end} · unique users = distinct visitors · resolved = lead captured or ended without handoff
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <select
            className="search"
            style={{ width: '140px' }}
            value={days}
            onChange={(event) => setDays(Number(event.target.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <Button variant="secondary" onClick={() => exportCsv('conversations')}>Conversations CSV</Button>
          <Button variant="secondary" onClick={() => exportCsv('unanswered')}>Unanswered CSV</Button>
        </div>
      </div>

      <div className="grid metric-grid">
        <StatCard label="Conversations" value={totals.conversations ?? 0} />
        <StatCard label="Unique users" value={totals.unique_users ?? 0} />
        <StatCard label="Messages" value={totals.messages ?? 0} />
        <StatCard label="Leads" value={totals.leads ?? 0} />
        <StatCard label="Handoffs" value={totals.handoffs ?? 0} />
        <StatCard label="Resolution rate" value={hasData ? `${totals.resolution_rate ?? 0}%` : '—'} />
      </div>

      <div
        className="card"
        style={{
          marginTop: '14px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '18px',
          padding: '12px 16px',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '12px', fontWeight: 600 }}>
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: live ? '#16a34a' : '#c0c4cc',
              boxShadow: live ? '0 0 0 3px rgba(22,163,74,0.15)' : 'none',
            }}
          />
          {live ? 'Live' : 'Not connected'}
        </span>
        {live && (
          <>
            <LiveStat label="Active now" value={live.active_now} />
            <LiveStat label="Chats today" value={live.today?.conversations} />
            <LiveStat label="Messages today" value={live.today?.messages} />
            <LiveStat label="Contacts today" value={live.today?.leads} />
            <LiveStat label="Meetings today" value={live.today?.meetings} />
            <span className="muted" style={{ marginLeft: 'auto', fontSize: '11.5px' }}>
              updated {new Date(live.generated_at).toLocaleTimeString()} · refreshes every 10s
            </span>
          </>
        )}
      </div>

      {!loading && !hasData && (
        <Card style={{ marginTop: '16px', textAlign: 'center', padding: '32px 20px' }}>
          <h3 style={{ fontSize: '16px', marginBottom: '6px' }}>No conversation data yet.</h3>
          <p className="muted" style={{ fontSize: '13px', maxWidth: '460px', margin: '0 auto' }}>
            These figures fill in from real chats. Nothing here is estimated.
          </p>
        </Card>
      )}

      {!loading && hasData && !compact && (
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '16px' }}>
          <Card>
            <h4 style={{ margin: '0 0 10px', fontSize: '14px' }}>Intent</h4>
            {['buying', 'renting', 'browsing', 'other'].map((key) => {
              const value = data.intents?.[key] || 0;
              const pct = totals.conversations ? Math.round((value / totals.conversations) * 100) : 0;
              return (
                <div key={key} style={{ marginBottom: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12.5px' }}>
                    <span style={{ textTransform: 'capitalize' }}>{key}</span>
                    <span className="muted">{value} · {pct}%</span>
                  </div>
                  <div style={{ height: '6px', background: '#f1eff8', borderRadius: '999px' }}>
                    <div style={{ width: `${pct}%`, height: '100%', background: '#6d4aff', borderRadius: '999px' }} />
                  </div>
                </div>
              );
            })}
          </Card>
          <Card>
            <h4 style={{ margin: '0 0 10px', fontSize: '14px' }}>Knowledge</h4>
            <p style={{ fontSize: '13px', margin: '0 0 6px' }}>
              {data.knowledge?.sources ?? 0} sources · {data.knowledge?.processed ?? 0} processed ·{' '}
              {data.knowledge?.failed ?? 0} failed
            </p>
            <p className="muted" style={{ fontSize: '12.5px', margin: '0 0 6px' }}>
              {data.knowledge?.unanswered_count ?? 0} unanswered questions
            </p>
            {(data.knowledge?.top_sources || []).length > 0 && (
              <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12.5px' }}>
                {data.knowledge.top_sources.map((row) => (
                  <li key={row.source}>{row.source} — {row.citations} citations</li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </div>
  );
};
