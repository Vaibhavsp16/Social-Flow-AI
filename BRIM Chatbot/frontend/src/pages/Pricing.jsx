import React from 'react';
import { useToast } from '../context/ToastContext';
import { Button } from '../components/Button';

export const Pricing = () => {
  const { showToast } = useToast();

  return (
    <div>
      <div style={{ textAlign: 'center', marginBottom: '36px' }}>
        <h1 style={{ fontSize: '32px' }}>Simple, transparent pricing</h1>
        <p className="muted" style={{ marginTop: '8px', fontSize: '15px' }}>
          Start free and upgrade as your chatbot traffic and needs grow.
        </p>
      </div>

      <div className="grid pricing">
        {/* Free Plan */}
        <div className="price-card">
          <h3>Free</h3>
          <p className="muted">For testing and personal exploration</p>
          <div className="price">
            ₹0 <small>/ month</small>
          </div>
          <Button variant="secondary" full disabled>
            Current plan
          </Button>
          <ul className="checklist">
            <li>1 chatbot</li>
            <li>100 conversations / mo</li>
            <li>Basic industry templates</li>
            <li>Public shareable link</li>
          </ul>
        </div>

        {/* Pro Plan */}
        <div className="price-card featured">
          <span className="tag">POPULAR</span>
          <h3>Pro</h3>
          <p className="muted">For growing businesses and startups</p>
          <div className="price">
            ₹1,999 <small>/ month</small>
          </div>
          <Button variant="primary" full onClick={() => showToast('Pro upgrade flow initiated')}>
            Upgrade to Pro
          </Button>
          <ul className="checklist">
            <li>10 chatbots</li>
            <li>5,000 conversations / mo</li>
            <li>Full knowledge ingestion</li>
            <li>Advanced analytics</li>
            <li>Custom instructions & personality</li>
            <li>Website embed widget</li>
          </ul>
        </div>

        {/* Business Plan */}
        <div className="price-card">
          <h3>Business</h3>
          <p className="muted">For enterprises and high volume teams</p>
          <div className="price">Custom</div>
          <Button variant="secondary" full onClick={() => showToast('Sales team contact modal opened')}>
            Contact sales
          </Button>
          <ul className="checklist">
            <li>Unlimited chatbots</li>
            <li>Unlimited conversations</li>
            <li>Dedicated LLM instance</li>
            <li>Custom integrations & SLA</li>
            <li>Priority 24/7 support</li>
          </ul>
        </div>
      </div>
    </div>
  );
};
