import React, { useEffect, useMemo, useState } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { StatCard } from '../components/StatCard';
import { useToast } from '../context/ToastContext';
import { analyticsService, rangeParams } from '../services/analyticsService';

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'users', label: 'Users' },
  { key: 'projects', label: 'Projects' },
  { key: 'bots', label: 'Bots' },
  { key: 'conversations', label: 'Conversations' },
  { key: 'leads', label: 'Leads' },
  { key: 'activity', label: 'Activity' },
];

const COLUMNS = {
  users: ['id', 'name', 'email', 'role', 'projects', 'bots', 'created_at'],
  projects: ['id', 'name', 'industry', 'owner', 'bots', 'created_at'],
  bots: ['id', 'name', 'status', 'project', 'owner', 'conversations', 'created_at'],
  conversations: ['id', 'bot', 'owner', 'intent', 'status', 'messages', 'started_at'],
  leads: ['id', 'created_at', 'bot', 'name', 'phone', 'email', 'preferred_contact', 'intent', 'status'],
  activity: ['created_at', 'event_type', 'actor', 'entity_type', 'entity_id'],
};

function cell(value) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'string' && value.includes('T')) {
    const parsed = new Date(value.endsWith('Z') ? value : `${value}Z`);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
    }
  }
  return String(value);
}

function Table({ columns, rows }) {
  if (!rows.length) {
    return <p className="muted" style={{ fontSize: '13px' }}>No records yet.</p>;
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12.5px' }}>
        <thead>
          <tr style={{ textAlign: 'left', color: '#6f7184' }}>
            {columns.map((column) => (
              <th key={column} style={{ padding: '8px 10px', whiteSpace: 'nowrap' }}>
                {column.replace(/_/g, ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.id ?? index} style={{ borderTop: '1px solid #f0eef7' }}>
              {columns.map((column) => (
                <td key={column} style={{ padding: '8px 10px', whiteSpace: 'nowrap' }}>
                  {cell(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const Admin = () => {
  const { showToast } = useToast();
  const [tab, setTab] = useState('overview');
  const [days, setDays] = useState(30);
  const [overview, setOverview] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);

  const params = useMemo(() => rangeParams(days), [days]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const load = async () => {
      try {
        if (tab === 'overview') {
          const payload = await analyticsService.admin.overview(params);
          if (!cancelled) setOverview(payload);
        } else if (tab === 'activity') {
          const payload = await analyticsService.admin.activity({ limit: 200 });
          if (!cancelled) setRows(payload.items || []);
        } else {
          const payload = await analyticsService.admin[tab]({ limit: 200 });
          if (!cancelled) setRows(payload.items || []);
        }
      } catch (error) {
        if (!cancelled) {
          // 403 means "not an administrator" — say so instead of rendering an empty console.
          if (error?.response?.status === 403) {
            setForbidden(true);
          } else {
            showToast?.('Could not load admin data.');
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [tab, params, showToast]);

  const exportCsv = async (kind) => {
    try {
      await analyticsService.admin.downloadCsv(kind, params);
      showToast?.(`${kind} CSV downloaded.`);
    } catch {
      showToast?.('Export failed.');
    }
  };

  if (forbidden) {
    return (
      <div>
        <div className="page-head">
          <div>
            <h1>Admin console</h1>
            <p className="muted">Platform-wide data. Customer contact details are masked.</p>
          </div>
        </div>
        <Card style={{ textAlign: 'center', padding: '48px 20px' }}>
          <h2 style={{ fontSize: '18px', marginBottom: '8px' }}>Administrator access required</h2>
          <p className="muted" style={{ maxWidth: '460px', margin: '0 auto', fontSize: '13px' }}>
            This account is a business account. Platform data is limited to administrators.
            Everything for your own bots is available under Analytics and My Bots.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Admin console</h1>
          <p className="muted">Platform-wide data. Customer contact details are masked.</p>
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
          <Button variant="secondary" onClick={() => exportCsv('bot_usage')}>Bot usage CSV</Button>
          <Button variant="secondary" onClick={() => exportCsv('leads')}>Leads CSV</Button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '18px' }}>
        {TABS.map((item) => (
          <button
            key={item.key}
            onClick={() => setTab(item.key)}
            style={{
              border: '1px solid',
              borderColor: tab === item.key ? '#6d4aff' : '#e7e4f3',
              background: tab === item.key ? '#f3f0ff' : '#fff',
              color: tab === item.key ? '#4b2fd6' : '#4b5563',
              borderRadius: '999px',
              padding: '7px 14px',
              fontSize: '12.5px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      {loading && <p className="muted">Loading…</p>}

      {!loading && tab === 'overview' && overview && (
        <>
          <div className="grid metric-grid">
            <StatCard label="Users" value={overview.entities.users} />
            <StatCard label="Projects" value={overview.entities.projects} />
            <StatCard label="Bots" value={overview.entities.bots} />
            <StatCard label="Conversations" value={overview.totals.conversations} />
            <StatCard label="Leads" value={overview.totals.leads} />
            <StatCard label="Open handoffs" value={overview.entities.handoffs_open} />
          </div>

          {!overview.has_data && (
            <Card style={{ marginTop: '20px' }}>
              <h2 style={{ fontSize: '16px', marginBottom: '6px' }}>No conversation data yet.</h2>
              <p className="muted" style={{ fontSize: '13px' }}>
                Bots, projects and users above come from stored records; conversation metrics stay at zero
                until visitors start chatting.
              </p>
            </Card>
          )}

          {overview.has_data && (
            <Card style={{ marginTop: '20px' }}>
              <h2 style={{ fontSize: '16px', marginBottom: '10px' }}>Busiest bots</h2>
              <Table
                columns={['bot_name', 'status', 'conversations', 'messages', 'leads', 'handoffs']}
                rows={(overview.per_bot || []).slice(0, 10)}
              />
            </Card>
          )}
        </>
      )}

      {!loading && tab !== 'overview' && (
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
            <h2 style={{ fontSize: '16px' }}>{TABS.find((item) => item.key === tab)?.label}</h2>
            <span className="muted" style={{ fontSize: '12px' }}>{rows.length} shown</span>
          </div>
          <Table columns={COLUMNS[tab] || []} rows={rows} />
        </Card>
      )}
    </div>
  );
};
