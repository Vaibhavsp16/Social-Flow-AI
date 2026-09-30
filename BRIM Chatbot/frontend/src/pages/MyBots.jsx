import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { botService } from '../services/botService';
import { Button } from '../components/Button';
import { BotCard } from '../components/BotCard';
import { LoadingState } from '../components/LoadingState';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';

export const MyBots = () => {
  const navigate = useNavigate();
  const [bots, setBots] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchBots = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await botService.getBots();
      setBots(data || []);
    } catch (err) {
      setError(err.userMessage || 'Failed to load bots.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBots();
  }, []);

  const filteredBots = bots.filter((b) =>
    b.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (b.industry && b.industry.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (b.description && b.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>My Bots</h1>
          <p className="muted">Create, configure and manage your chatbot assistants.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <input
            className="search"
            placeholder="Search bots..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <Button variant="primary" onClick={() => navigate('/bots/create')}>
            + Create New Bot
          </Button>
        </div>
      </div>

      {loading ? (
        <LoadingState message="Loading your bots..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchBots} />
      ) : bots.length === 0 ? (
        <EmptyState
          icon="⚡"
          title="No chatbots created yet"
          description="Build your first AI chatbot customized for your industry in just a few steps."
          actionLabel="+ Create New Bot"
          onAction={() => navigate('/bots/create')}
        />
      ) : filteredBots.length === 0 ? (
        <EmptyState
          icon="🔍"
          title="No bots match your search"
          description="Try searching with a different term or keyword."
          actionLabel="Clear Search"
          onAction={() => setSearchTerm('')}
        />
      ) : (
        <div className="grid bots">
          {filteredBots.map((bot) => (
            <BotCard
              key={bot.id}
              bot={bot}
              onClick={() => navigate(`/bots/${bot.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
};
