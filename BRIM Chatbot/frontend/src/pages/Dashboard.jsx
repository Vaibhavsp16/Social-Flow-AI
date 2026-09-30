import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { botService } from '../services/botService';
import { projectService } from '../services/projectService';
import { Button } from '../components/Button';
import { StatCard } from '../components/StatCard';
import { BotCard } from '../components/BotCard';
import { LoadingState } from '../components/LoadingState';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';

export const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [bots, setBots] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [botsData, projectsData] = await Promise.all([
        botService.getBots(),
        projectService.getProjects(),
      ]);
      setBots(botsData || []);
      setProjects(projectsData || []);
    } catch (err) {
      setError(err.userMessage || 'Failed to load dashboard data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const liveBotsCount = bots.filter((b) => b.status === 'Live').length;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Good morning, {user?.name || 'User'}</h1>
          <p className="muted">Manage your AI assistants and projects from one place.</p>
        </div>
        <Button variant="primary" onClick={() => navigate('/bots/create')}>
          + Create New Bot
        </Button>
      </div>

      <div className="grid stats">
        <StatCard
          label="Total bots"
          value={bots.length}
          delta={liveBotsCount > 0 ? `${liveBotsCount} live` : '0 active'}
        />
        <StatCard
          label="Active projects"
          value={projects.length}
          delta={projects.length > 0 ? `${projects.length} configured` : 'None yet'}
        />
        <StatCard
          label="Conversations"
          value="0"
          delta="Real-time ready"
        />
        <StatCard
          label="Plan"
          value="Starter"
          delta="Free tier"
        />
      </div>

      <div className="page-head" style={{ marginTop: '36px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: '700' }}>Your bots</h2>
          <p className="muted">Open a bot to manage its settings and view details.</p>
        </div>
        {bots.length > 0 && (
          <Button variant="secondary" onClick={() => navigate('/bots')}>
            View all
          </Button>
        )}
      </div>

      {loading ? (
        <LoadingState message="Fetching your bots..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchData} />
      ) : bots.length === 0 ? (
        <EmptyState
          icon="🤖"
          title="No bots yet"
          description="Create your first chatbot to start assisting customers with your business knowledge."
          actionLabel="+ Create Your First Bot"
          onAction={() => navigate('/bots/create')}
        />
      ) : (
        <div className="grid bots">
          {bots.map((bot) => (
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
