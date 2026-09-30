import React from 'react';
import { useToast } from '../context/ToastContext';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { StatCard } from '../components/StatCard';

export const Analytics = () => {
  const { showToast } = useToast();

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Reporting & Analytics</h1>
          <p className="muted">A workspace-level view of chatbot performance and business outcomes.</p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <select className="search" style={{ width: '150px' }}>
            <option>Last 30 days</option>
            <option>Last 7 days</option>
            <option>Last 90 days</option>
          </select>
          <Button variant="secondary" onClick={() => showToast('Workspace report exported')}>
            Export report
          </Button>
        </div>
      </div>

      <div className="grid metric-grid">
        <StatCard label="Total conversations" value="0" delta="No sessions yet" />
        <StatCard label="Unique users" value="0" delta="No traffic yet" />
        <StatCard label="Resolution rate" value="—" />
        <StatCard label="Human handoff" value="0%" />
        <StatCard label="Lead captures" value="0" />
        <StatCard label="Avg. response time" value="< 1.0s" />
      </div>

      <Card style={{ marginTop: '24px', textAlign: 'center', padding: '60px 20px' }}>
        <div style={{ fontSize: '36px', marginBottom: '14px' }}>📊</div>
        <h2 style={{ fontSize: '18px', marginBottom: '8px' }}>Workspace Analytics Hub</h2>
        <p className="muted" style={{ maxWidth: '480px', margin: '0 auto' }}>
          Analytics will appear once your bots start receiving live customer queries.
        </p>
      </Card>
    </div>
  );
};
