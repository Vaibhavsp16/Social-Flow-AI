import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { botService } from '../services/botService';
import { useToast } from '../context/ToastContext';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { Select } from '../components/Select';
import { Card } from '../components/Card';
import { StatCard } from '../components/StatCard';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import { PREDEFINED_INDUSTRIES } from '../constants/industries';
import { KnowledgeManager } from '../components/KnowledgeManager';
import { knowledgeService } from '../services/knowledgeService';
import { chatService } from '../services/chatService';

export const BotOverview = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [bot, setBot] = useState(null);
  const [knowledgeList, setKnowledgeList] = useState([]);
  const [conversations, setConversations] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  // Edit form state
  const [editData, setEditData] = useState({
    name: '',
    industry: 'Real Estate',
    description: '',
    language: 'English',
    personality: 'Friendly & professional',
    welcome_message: '',
    status: 'Live',
    shareable_slug: '',
  });
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveError, setSaveError] = useState('');

  const fetchBotDetails = async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, kSources, convos] = await Promise.all([
        botService.getBot(id),
        knowledgeService.getBotKnowledge(id).catch(() => []),
        chatService.listConversations(id, 200).catch(() => null),
      ]);
      setBot(data);
      setKnowledgeList(kSources || []);
      setConversations(Array.isArray(convos) ? convos : null);
      setEditData({
        name: data.name || '',
        industry: data.project?.industry || 'Real Estate',
        description: data.description || '',
        language: data.language || 'English',
        personality: data.personality || 'Friendly & professional',
        welcome_message: data.welcome_message || '',
        status: data.status || 'Live',
        shareable_slug: data.shareable_slug || '',
      });
    } catch (err) {
      setError(err.userMessage || 'Failed to load bot details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) {
      fetchBotDetails();
    }
  }, [id]);

  const handleKnowledgeChange = (sources) => {
    setKnowledgeList(sources || []);
  };

  const handleSaveDetails = async (e) => {
    e.preventDefault();
    if (!editData.name.trim()) {
      setSaveError('Bot name cannot be empty.');
      return;
    }

    setSaveLoading(true);
    setSaveError('');

    try {
      const updated = await botService.updateBot(id, {
        name: editData.name.trim(),
        industry: editData.industry,
        description: editData.description.trim(),
        language: editData.language,
        personality: editData.personality,
        welcome_message: editData.welcome_message.trim(),
        status: editData.status,
        shareable_slug: editData.shareable_slug.trim(),
      });
      setBot(updated);
      showToast('Bot changes saved successfully to database!');
    } catch (err) {
      setSaveError(err.userMessage || 'Failed to save changes.');
    } finally {
      setSaveLoading(false);
    }
  };

  const copyShareLink = () => {
    if (!bot) return;
    const shareUrl = `https://chat.brim.ai/${bot.shareable_slug}`;
    navigator.clipboard?.writeText(shareUrl);
    showToast('Shareable link copied to clipboard!');
  };

  if (loading) return <LoadingState message="Loading bot details..." />;
  if (error) return <ErrorState message={error} onRetry={fetchBotDetails} />;
  if (!bot) return <ErrorState title="Bot not found" message="This bot does not exist or you do not have permission." />;

  const shareUrl = `https://chat.brim.ai/${bot.shareable_slug}`;
  const formattedCreatedDate = new Date(bot.created_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
  const formattedUpdatedDate = new Date(bot.updated_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });

  const docsCount = knowledgeList.filter((s) => s.source_type === 'DOCUMENT').length;
  const imagesCount = knowledgeList.filter((s) => s.source_type === 'IMAGE').length;
  const webCount = knowledgeList.filter((s) => s.source_type === 'WEBSITE').length;
  const instrCount = knowledgeList.filter((s) => s.source_type === 'INSTRUCTION').length;
  const socialCount = knowledgeList.filter((s) => s.source_type === 'SOCIAL_LINK').length;

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'knowledge', label: `Knowledge Base (${knowledgeList.length})` },
    { id: 'chats', label: 'Chat History' },
    { id: 'details', label: 'Bot Details' },
    { id: 'link', label: 'Share & Deploy' },
    { id: 'analytics', label: 'Analytics' },
  ];

  return (
    <div>
      <div className="detail-head">
        <div>
          <h1>{bot.name}</h1>
          <p className="muted">
            {bot.project?.industry || 'General'} ·{' '}
            <span className={`status ${bot.status === 'Live' ? '' : 'draft'}`}>
              <span className="dot"></span>
              {bot.status}
            </span>
          </p>
        </div>
        <Button variant="primary" onClick={() => navigate(`/preview/${bot.id}`)}>
          Preview Chat
        </Button>
      </div>

      <div className="tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={activeTab === tab.id ? 'active' : ''}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* OVERVIEW TAB */}
      {activeTab === 'overview' && (
        <div>
          <div className="grid stats">
            <StatCard
              label="Conversations"
              value={conversations === null ? '—' : conversations.length}
              delta={conversations && conversations.length ? 'Recorded sessions' : 'No sessions yet'}
            />
            <StatCard
              label="Knowledge sources"
              value={knowledgeList.length}
              delta={
                knowledgeList.length === 0
                  ? 'Nothing indexed yet'
                  : `${knowledgeList.reduce((sum, s) => sum + (s.chunks_count || 0), 0)} chunks indexed`
              }
            />
            <StatCard label="Language" value={bot.language} />
            <StatCard label="Status" value={bot.status} delta={`Updated ${formattedUpdatedDate}`} />
          </div>

          <div className="grid" style={{ gridTemplateColumns: '1.35fr 0.65fr', marginTop: '20px' }}>
            <Card>
              <h3 style={{ marginBottom: '8px' }}>Bot Information</h3>
              <p className="muted" style={{ marginBottom: '16px' }}>
                Core configuration and personality profile.
              </p>
              <div style={{ display: 'grid', gap: '10px', fontSize: '13.5px' }}>
                <p>
                  <b>Welcome Message:</b> "{bot.welcome_message}"
                </p>
                <p>
                  <b>Industry:</b> {bot.project?.industry || 'General'}
                </p>
                <p>
                  <b>Personality:</b> {bot.personality}
                </p>
                <p>
                  <b>Description:</b> {bot.description || 'No description added.'}
                </p>
                <p>
                  <b>Public Slug:</b> <code>{bot.shareable_slug}</code>
                </p>
                <p>
                  <b>Created on:</b> {formattedCreatedDate}
                </p>
              </div>
            </Card>

            <Card>
              <h3>Bot health</h3>
              <p style={{ marginTop: '8px' }}>
                <span className={`status ${bot.status === 'Live' ? '' : 'draft'}`}>
                  ● {bot.status}
                </span>
              </p>
              <p style={{ marginTop: '14px' }}>
                <b>Knowledge sources</b>
                <br />
                <span className="muted">
                  {knowledgeList.length === 0
                    ? 'No sources added yet'
                    : `${docsCount} docs · ${webCount} web · ${imagesCount} images · ${instrCount} prompt rules`}
                </span>
              </p>
              <p style={{ marginTop: '14px' }}>
                <b>Last updated</b>
                <br />
                <span className="muted">{formattedUpdatedDate}</span>
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '16px' }}>
                <Button
                  variant="primary"
                  full
                  onClick={() => navigate(`/chat/${bot.id}`)}
                >
                  💬 Open Interactive Chat
                </Button>
                <Button
                  variant="secondary"
                  full
                  onClick={() => setActiveTab('knowledge')}
                >
                  Manage Knowledge Base
                </Button>
                <Button
                  variant="secondary"
                  full
                  onClick={() => setActiveTab('details')}
                >
                  Edit bot settings
                </Button>
              </div>
            </Card>
          </div>

          <Card style={{ marginTop: '20px', textAlign: 'center', padding: '34px 20px' }}>
            <div style={{ fontSize: '28px', marginBottom: '8px' }}>📊</div>
            <h3 style={{ fontSize: '16px', marginBottom: '6px' }}>Analytics & Activity</h3>
            <p className="muted" style={{ maxWidth: '460px', margin: '0 auto 16px' }}>
              Analytics will appear once your bot starts receiving conversations.
            </p>
            <Button variant="secondary" onClick={() => navigate(`/preview/${bot.id}`)}>
              Test Conversation in Preview
            </Button>
          </Card>
        </div>
      )}

      {/* KNOWLEDGE BASE TAB */}
      {activeTab === 'knowledge' && (
        <div>
          <div className="page-head" style={{ marginBottom: '18px' }}>
            <div>
              <h2 style={{ margin: 0 }}>Chatbot Knowledge Base</h2>
              <p className="muted">
                Manage documents, URLs, social profiles, and prompt instructions for <b>{bot.name}</b>.
              </p>
            </div>
          </div>
          <KnowledgeManager botId={bot.id} onSourcesChange={handleKnowledgeChange} />
        </div>
      )}

      {/* CHATS TAB */}
      {activeTab === 'chats' && (
        <Card>
          <div className="page-head">
            <div>
              <h3 style={{ margin: 0 }}>Chat History</h3>
              <p className="muted">Review and inspect individual user conversations.</p>
            </div>
          </div>

          {conversations && conversations.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '16px' }}>
              {conversations.map((c) => (
                <div
                  key={c.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '14px',
                    border: '1px solid var(--line)',
                    borderRadius: '10px',
                    background: '#fff',
                  }}
                >
                  <div>
                    <b style={{ fontSize: '14px', display: 'block' }}>Conversation #{c.id}</b>
                    <span className="muted" style={{ fontSize: '12px' }}>
                      {c.message_count} messages · {new Date(c.started_at).toLocaleString()} · intent: {c.intent || 'browsing'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span className={`status ${c.status === 'ACTIVE' ? '' : 'draft'}`}>
                      <span className="dot"></span>
                      {c.status}
                    </span>
                    <Button variant="secondary" onClick={() => navigate(`/chat/${bot.id}?convo=${c.id}`)}>
                      Open
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty" style={{ margin: '20px 0' }}>
              <div className="empty-icon">💬</div>
              <h3>No conversations recorded yet</h3>
              <p>Once users start chatting with this bot, their message logs will be saved and listed here.</p>
              <Button variant="primary" onClick={() => navigate(`/chat/${bot.id}`)}>
                Start a Chat
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* DETAILS TAB (EDIT BOT) */}
      {activeTab === 'details' && (
        <div className="grid" style={{ gridTemplateColumns: '1.2fr 0.8fr' }}>
          <Card>
            <h3 style={{ marginBottom: '4px' }}>Edit Bot Information</h3>
            <p className="muted" style={{ marginBottom: '16px' }}>
              Update your bot configuration in PostgreSQL database.
            </p>

            {saveError && (
              <div
                style={{
                  background: '#fee2e2',
                  border: '1px solid #fca5a5',
                  color: '#b91c1c',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  fontSize: '13px',
                  marginBottom: '14px',
                }}
              >
                {saveError}
              </div>
            )}

            <form onSubmit={handleSaveDetails}>
              <Input
                label="Bot name"
                required
                value={editData.name}
                onChange={(e) => setEditData({ ...editData, name: e.target.value })}
              />

              <Select
                label="Industry"
                options={PREDEFINED_INDUSTRIES}
                value={editData.industry}
                onChange={(e) => setEditData({ ...editData, industry: e.target.value })}
              />

              <div className="field">
                <label>Short Description</label>
                <textarea
                  rows="3"
                  value={editData.description}
                  onChange={(e) => setEditData({ ...editData, description: e.target.value })}
                  placeholder="Describe what your bot helps with..."
                />
              </div>

              <div className="form-grid">
                <Select
                  label="Status"
                  options={['Live', 'Draft']}
                  value={editData.status}
                  onChange={(e) => setEditData({ ...editData, status: e.target.value })}
                />

                <Select
                  label="Language"
                  options={['English', 'Hindi', 'Gujarati', 'Tamil', 'Spanish', 'French', 'German']}
                  value={editData.language}
                  onChange={(e) => setEditData({ ...editData, language: e.target.value })}
                />
              </div>

              <Select
                label="Personality"
                options={['Friendly & professional', 'Professional', 'Casual', 'Concise']}
                value={editData.personality}
                onChange={(e) => setEditData({ ...editData, personality: e.target.value })}
              />

              <div className="field">
                <label>Welcome Message</label>
                <textarea
                  rows="3"
                  value={editData.welcome_message}
                  onChange={(e) => setEditData({ ...editData, welcome_message: e.target.value })}
                />
              </div>

              <Input
                label="Shareable Slug"
                value={editData.shareable_slug}
                onChange={(e) => setEditData({ ...editData, shareable_slug: e.target.value })}
                placeholder="custom-slug"
              />

              <div style={{ marginTop: '20px' }}>
                <Button type="submit" variant="primary" loading={saveLoading}>
                  Save changes
                </Button>
              </div>
            </form>
          </Card>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Card>
              <h3>Knowledge Sources</h3>
              <p className="muted" style={{ margin: '8px 0 14px', fontSize: '13px' }}>
                Manage the knowledge bases connected to this bot.
              </p>
              <div style={{ display: 'grid', gap: '8px', fontSize: '13px' }}>
                <p>📄 Documents ({docsCount} uploaded)</p>
                <p>🌐 Websites ({webCount} linked)</p>
                <p>🖼 Images ({imagesCount} uploaded)</p>
                <p>🔗 Social profiles ({socialCount} linked)</p>
                <p>✦ Custom prompt instructions ({instrCount})</p>
              </div>
              <Button
                variant="secondary"
                full
                style={{ marginTop: '16px' }}
                onClick={() => setActiveTab('knowledge')}
              >
                Manage sources
              </Button>
            </Card>

            <Card>
              <h3>Danger Zone</h3>
              <p className="muted" style={{ margin: '8px 0 14px', fontSize: '13px' }}>
                Permanently delete this chatbot and its configuration.
              </p>
              <Button
                variant="danger"
                full
                onClick={async () => {
                  if (window.confirm(`Are you sure you want to delete "${bot.name}"?`)) {
                    try {
                      await botService.deleteBot(bot.id);
                      showToast('Bot deleted successfully.');
                      navigate('/dashboard');
                    } catch (err) {
                      showToast(err.userMessage || 'Failed to delete bot.');
                    }
                  }
                }}
              >
                Delete this bot
              </Button>
            </Card>
          </div>
        </div>
      )}

      {/* LINK & DEPLOY TAB */}
      {activeTab === 'link' && (
        <Card style={{ maxWidth: '820px' }}>
          <h3>Share & Deploy</h3>
          <p className="muted">Give customers a public link or prepare the chatbot for website embedding.</p>

          <div className="link-box">
            <input readOnly value={shareUrl} />
            <Button variant="primary" onClick={copyShareLink}>
              Copy link
            </Button>
          </div>

          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: '20px' }}>
            <div className="card">
              <b>Public link</b>
              <p className="muted" style={{ fontSize: '13px', margin: '6px 0 14px' }}>
                Anyone with the link can access and chat with your assistant.
              </p>
              <Button variant="secondary" onClick={() => navigate(`/preview/${bot.id}`)}>
                Open chatbot
              </Button>
            </div>

            <div className="card">
              <b>Website embed</b>
              <p className="muted" style={{ fontSize: '13px', margin: '6px 0 14px' }}>
                Embed the chatbot widget script on your website.
              </p>
              <Button
                variant="secondary"
                onClick={() =>
                  showToast(
                    `<script src="https://cdn.brim.ai/widget.js" data-bot="${bot.shareable_slug}"></script>`
                  )
                }
              >
                Get embed code
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* ANALYTICS TAB */}
      {activeTab === 'analytics' && (
        <div>
          <div className="page-head">
            <div>
              <h2 style={{ margin: 0 }}>Bot Reporting & Metrics</h2>
              <p className="muted">Performance, engagement, outcomes and content insights.</p>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <select className="search" style={{ width: '150px' }}>
                <option>Last 30 days</option>
                <option>Last 7 days</option>
                <option>Last 90 days</option>
              </select>
              <Button variant="secondary" onClick={() => showToast('Report export downloaded')}>
                Export report
              </Button>
            </div>
          </div>

          <Card style={{ textAlign: 'center', padding: '50px 20px', margin: '20px 0' }}>
            <div style={{ fontSize: '32px', marginBottom: '12px' }}>📈</div>
            <h3>Analytics will appear once your bot starts receiving conversations.</h3>
            <p className="muted" style={{ maxWidth: '440px', margin: '8px auto 18px' }}>
              When customers interact with your assistant, metrics like resolution rate, sentiment, and volume will populate in real time.
            </p>
            <Button variant="primary" onClick={() => navigate(`/preview/${bot.id}`)}>
              Test Bot in Chat Preview
            </Button>
          </Card>
        </div>
      )}
    </div>
  );
};
