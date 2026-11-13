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
import { BotMetrics } from '../components/BotMetrics';
import { ErrorState } from '../components/ErrorState';
import { PREDEFINED_INDUSTRIES } from '../constants/industries';
import {
  USE_CASE_OPTIONS,
  RESPONSE_STYLE_OPTIONS,
  LEAD_COLLECTION_OPTIONS,
  HANDOFF_OPTIONS,
  styleToKey,
  leadPolicyToKey,
  handoffToKey,
  useCaseToKey,
  keyToLabel,
} from '../constants/behaviour';

const labelForUseCase = (key) => keyToLabel(USE_CASE_OPTIONS, key, 'General assistant');
const labelForStyle = (key) => keyToLabel(RESPONSE_STYLE_OPTIONS, key, 'Simple & clear');
const labelForLeadPolicy = (key) => keyToLabel(LEAD_COLLECTION_OPTIONS, key, 'When relevant');
const labelForHandoff = (key) => keyToLabel(HANDOFF_OPTIONS, key, 'Allow when needed');
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
  const [embed, setEmbed] = useState(null);
  const [domain, setDomain] = useState(null);
  const [domainInput, setDomainInput] = useState('');
  const [domainBusy, setDomainBusy] = useState(false);
  const [domainError, setDomainError] = useState('');
  const [leads, setLeads] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [leadsLoading, setLeadsLoading] = useState(false);

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
        // Behaviour, not decoration: these four change how every reply is written.
        primary_use_case: data.primary_use_case || 'general_assistant',
        response_style: data.response_style || 'simple_clear',
        lead_collection: data.lead_collection || 'when_relevant',
        human_handoff: data.human_handoff || 'allow_when_needed',
        company_name: data.company_name || '',
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

  // Deployment details only matter on the Share & Deploy tab, so they load when it opens.
  useEffect(() => {
    if (bot && activeTab === 'link') {
      loadDeployInfo();
    }
  }, [bot, activeTab]);

  // Leads and meetings are the reason the bot exists, so they load with their own tab.
  useEffect(() => {
    if (!bot || activeTab !== 'leads') return;
    let cancelled = false;
    setLeadsLoading(true);
    Promise.all([botService.getLeads(bot.id), botService.getMeetings(bot.id)])
      .then(([leadRows, meetingRows]) => {
        if (cancelled) return;
        setLeads(Array.isArray(leadRows) ? leadRows : leadRows?.leads || []);
        setMeetings(Array.isArray(meetingRows) ? meetingRows : meetingRows?.meetings || []);
      })
      .catch(() => {
        if (!cancelled) {
          setLeads([]);
          setMeetings([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLeadsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [bot, activeTab]);

  const downloadLeadsCsv = () => {
    if (!bot) return;
    const token = localStorage.getItem('brim_auth_token');
    const base = (import.meta.env.VITE_API_URL || 'http://localhost:8000/api').replace(/\/$/, '');
    // Straight to the endpoint so the browser handles the download and the filename.
    fetch(`${base}/bots/${bot.id}/leads.csv`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((response) => {
        if (!response.ok) throw new Error('Export failed');
        return response.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `leads_${bot.shareable_slug}.csv`;
        anchor.click();
        URL.revokeObjectURL(url);
        showToast('Leads CSV downloaded.');
      })
      .catch(() => showToast('Could not export leads.'));
  };

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
        primary_use_case: editData.primary_use_case,
        response_style: editData.response_style,
        lead_collection: editData.lead_collection,
        human_handoff: editData.human_handoff,
        company_name: editData.company_name.trim(),
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
    navigator.clipboard?.writeText(shareUrl);
    showToast('Shareable link copied to clipboard!');
  };

  const loadDeployInfo = async () => {
    if (!bot) return;
    try {
      const info = await botService.getEmbedSnippet(bot.shareable_slug);
      setEmbed(info);
    } catch (err) {
      // The page still works without the snippet: the embed code is built locally as a fallback.
      setEmbed(null);
    }
    try {
      setDomain(await botService.getDomain(bot.id));
    } catch (err) {
      setDomain(null);
    }
  };

  const saveDomain = async () => {
    setDomainBusy(true);
    setDomainError('');
    try {
      const result = await botService.setDomain(bot.id, domainInput.trim());
      setDomain(result);
      setDomainInput(result.domain || '');
      showToast(
        result.domain
          ? 'Domain saved. Add the DNS records, then verify.'
          : 'Custom domain removed.'
      );
    } catch (err) {
      setDomainError(err.userMessage || 'Could not save the domain.');
    } finally {
      setDomainBusy(false);
    }
  };

  const verifyDomainNow = async () => {
    setDomainBusy(true);
    setDomainError('');
    try {
      const result = await botService.verifyDomain(bot.id);
      setDomain(result);
      if (result.status === 'verified') {
        showToast('Domain verified — the chatbot is live on your domain.');
      } else {
        setDomainError(
          result.message ||
            'Not verified yet. DNS changes can take a few minutes to propagate.'
        );
      }
    } catch (err) {
      setDomainError(err.userMessage || 'Verification failed.');
    } finally {
      setDomainBusy(false);
    }
  };

  if (loading) return <LoadingState message="Loading bot details..." />;
  if (error) return <ErrorState message={error} onRetry={fetchBotDetails} />;
  if (!bot) return <ErrorState title="Bot not found" message="This bot does not exist or you do not have permission." />;

  // Built from the deployment origin rather than a hardcoded host: the old `chat.brim.ai` URL did
  // not resolve, so every "public link" was a dead end.
  const publicBase = (import.meta.env.VITE_PUBLIC_APP_URL || window.location.origin).replace(/\/$/, '');
  const shareUrl = `${publicBase}/p/${bot.shareable_slug}`;
  const embedSnippet =
    embed?.snippet ||
    `<script src="${(import.meta.env.VITE_API_URL || 'http://localhost:8000/api').replace(/\/$/, '')}/public/widget.js" data-bot="${bot.shareable_slug}" async></script>`;
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
    { id: 'leads', label: 'Leads & Meetings' },
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
          <BotMetrics botId={bot.id} compact />
          <div className="grid stats" style={{ marginTop: '18px' }}>
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
              <p className="muted" style={{ marginBottom: '12px' }}>
                Core configuration and personality profile.
              </p>
              {/* The settings that change how every reply is written, visible without opening the
                  editor — otherwise a bot looks identical to every other bot on this page. */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
                <span className="status">{labelForUseCase(bot.primary_use_case)}</span>
                <span className="status">{labelForStyle(bot.response_style)}</span>
                <span className="status">Leads: {labelForLeadPolicy(bot.lead_collection)}</span>
                <span className="status">{labelForHandoff(bot.human_handoff)}</span>
              </div>
              <div style={{ display: 'grid', gap: '10px', fontSize: '13.5px' }}>
                <p>
                  {/* What a visitor actually sees. `welcome_message` is only the stored
                      configuration and can differ from the generated greeting. */}
                  <b>Welcome Message:</b>{' '}
                  {String(bot.greeting_preview || bot.welcome_message || '').includes('\n') ? (
                    <span style={{ whiteSpace: 'pre-line' }}>
                      "{(bot.greeting_preview || bot.welcome_message).trim()}"
                    </span>
                  ) : (
                    <span>"{bot.greeting_preview || bot.welcome_message}"</span>
                  )}
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

              {/* These four are what make two bots with the same knowledge behave differently. */}
              <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <Select
                  label="Primary use case"
                  options={USE_CASE_OPTIONS.map((o) => o.label)}
                  value={labelForUseCase(editData.primary_use_case)}
                  onChange={(e) =>
                    setEditData({ ...editData, primary_use_case: useCaseToKey(e.target.value) })
                  }
                />
                <Select
                  label="Response style"
                  options={RESPONSE_STYLE_OPTIONS.map((o) => o.label)}
                  value={labelForStyle(editData.response_style)}
                  onChange={(e) =>
                    setEditData({ ...editData, response_style: styleToKey(e.target.value) })
                  }
                />
                <Select
                  label="Lead collection"
                  options={LEAD_COLLECTION_OPTIONS.map((o) => o.label)}
                  value={labelForLeadPolicy(editData.lead_collection)}
                  onChange={(e) =>
                    setEditData({ ...editData, lead_collection: leadPolicyToKey(e.target.value) })
                  }
                />
                <Select
                  label="Human handoff"
                  options={HANDOFF_OPTIONS.map((o) => o.label)}
                  value={labelForHandoff(editData.human_handoff)}
                  onChange={(e) =>
                    setEditData({ ...editData, human_handoff: handoffToKey(e.target.value) })
                  }
                />
              </div>

              <Input
                label="Company name (used when the bot offers a callback)"
                value={editData.company_name}
                placeholder="e.g. Sharma Estates"
                onChange={(e) => setEditData({ ...editData, company_name: e.target.value })}
              />

              <div className="field">
                <label>Welcome Message</label>
                <textarea
                  rows="3"
                  value={editData.welcome_message}
                  onChange={(e) => setEditData({ ...editData, welcome_message: e.target.value })}
                />
                <span className="muted" style={{ fontSize: '12px' }}>
                  Shown as-is to visitors when you write your own. Leave it at the default to let
                  the assistant open with the standard greeting.
                </span>
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

      {/* LEADS & MEETINGS TAB */}
      {activeTab === 'leads' && (
        <Card>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              gap: '12px',
              flexWrap: 'wrap',
            }}
          >
            <div>
              <h3 style={{ margin: 0 }}>Leads & Meetings</h3>
              <p className="muted" style={{ fontSize: '13px', margin: '4px 0 0' }}>
                People who left contact details in the chat, and the calls or visits the bot
                arranged. The time shown is when they asked to be contacted.
              </p>
            </div>
            <Button variant="primary" onClick={downloadLeadsCsv}>
              Download CSV
            </Button>
          </div>

          {leadsLoading && <p className="muted" style={{ marginTop: '16px' }}>Loading…</p>}

          {!leadsLoading && leads.length === 0 && (
            <p className="muted" style={{ marginTop: '18px', fontSize: '13px' }}>
              No contact details captured yet. They appear here as soon as a visitor shares a number
              in the chat, or after an idle prompt.
            </p>
          )}

          {!leadsLoading && leads.length > 0 && (
            <div style={{ overflowX: 'auto', marginTop: '16px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: '#6b7280' }}>
                    <th style={{ padding: '8px 10px' }}>Name</th>
                    <th style={{ padding: '8px 10px' }}>Phone</th>
                    <th style={{ padding: '8px 10px' }}>Best time</th>
                    <th style={{ padding: '8px 10px' }}>Captured by</th>
                    <th style={{ padding: '8px 10px' }}>Meeting</th>
                    <th style={{ padding: '8px 10px' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.map((lead) => (
                    <tr key={lead.id} style={{ borderTop: '1px solid #eceef3' }}>
                      <td style={{ padding: '9px 10px' }}>{lead.name || '—'}</td>
                      <td style={{ padding: '9px 10px' }}>{lead.phone || '—'}</td>
                      <td style={{ padding: '9px 10px' }}>{lead.preferred_time || '—'}</td>
                      <td style={{ padding: '9px 10px', color: '#6b7280' }}>
                        {(lead.source || 'chat').replace(/_/g, ' ')}
                      </td>
                      <td style={{ padding: '9px 10px' }}>
                        {lead.meeting
                          ? `${lead.meeting.mode} · ${lead.meeting.preferred_slot || 'slot TBC'}`
                          : '—'}
                      </td>
                      <td style={{ padding: '9px 10px' }}>{lead.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {meetings.length > 0 && (
            <>
              <h4 style={{ marginTop: '26px', fontSize: '14px' }}>Scheduled</h4>
              <div style={{ display: 'grid', gap: '8px' }}>
                {meetings.map((meeting) => (
                  <div
                    key={meeting.id}
                    className="card"
                    style={{ padding: '12px 14px', fontSize: '13px' }}
                  >
                    <b>{meeting.name || 'Visitor'}</b> · {meeting.phone || 'no number'} ·{' '}
                    {meeting.mode}
                    <div className="muted" style={{ marginTop: '4px' }}>
                      {meeting.preferred_slot || 'Time to be confirmed'}
                      {meeting.scheduled_for
                        ? ` · ${new Date(meeting.scheduled_for).toLocaleString()}`
                        : ''}{' '}
                      · {meeting.status}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      )}

      {/* LINK & DEPLOY TAB */}
      {activeTab === 'link' && (
        <Card style={{ maxWidth: '860px' }}>
          <h3>Share & Deploy</h3>
          <p className="muted">
            A public page for this assistant, a widget you can paste into any site, and a domain you
            keep in your own name.
          </p>

          <div className="link-box">
            <input readOnly value={shareUrl} onFocus={(e) => e.target.select()} />
            <Button variant="primary" onClick={copyShareLink}>
              Copy link
            </Button>
          </div>

          {bot.status !== 'Live' && (
            <p className="muted" style={{ fontSize: '13px', marginTop: '10px' }}>
              This bot is a draft. Set its status to Live before sharing — the public page refuses
              drafts so an unfinished assistant is never published by accident.
            </p>
          )}

          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: '20px' }}>
            <div className="card">
              <b>Public link</b>
              <p className="muted" style={{ fontSize: '13px', margin: '6px 0 14px' }}>
                Opens the chatbot on its own page. No login needed.
              </p>
              <Button
                variant="secondary"
                onClick={() => window.open(shareUrl, '_blank', 'noopener,noreferrer')}
              >
                Open chatbot
              </Button>
            </div>

            <div className="card">
              <b>Website embed</b>
              <p className="muted" style={{ fontSize: '13px', margin: '6px 0 14px' }}>
                Paste this before <code>&lt;/body&gt;</code> on any page. It adds a launcher button
                that opens the assistant in an overlay.
              </p>
              <Button
                variant="secondary"
                onClick={() => {
                  navigator.clipboard?.writeText(embedSnippet);
                  showToast('Embed code copied. Paste it before </body> on your site.');
                }}
              >
                Copy embed code
              </Button>
            </div>
          </div>

          <div style={{ marginTop: '18px' }}>
            <b style={{ fontSize: '14px' }}>Embed snippet</b>
            <pre
              style={{
                background: '#0f1117',
                color: '#e6e8ee',
                padding: '14px',
                borderRadius: '10px',
                fontSize: '12.5px',
                overflowX: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                marginTop: '8px',
              }}
            >
              {embedSnippet}
            </pre>
            <p className="muted" style={{ fontSize: '12.5px' }}>
              The widget works on any domain. Inline embeds use{' '}
              <code>data-mode="inline"</code> plus <code>data-target="&lt;element-id&gt;"</code>.
            </p>
          </div>

          <hr style={{ margin: '26px 0', border: 0, borderTop: '1px solid #eceef3' }} />

          <b>Custom domain</b>
          <p className="muted" style={{ fontSize: '13px', margin: '6px 0 12px' }}>
            Your domain stays registered in your name — you point it at us, you do not transfer it.
          </p>

          <div className="link-box">
            <input
              placeholder="chat.yourcompany.com"
              value={domainInput}
              onChange={(e) => setDomainInput(e.target.value)}
            />
            <Button variant="secondary" onClick={saveDomain} disabled={domainBusy}>
              {domainBusy ? 'Saving…' : 'Save'}
            </Button>
            <Button
              variant="primary"
              onClick={verifyDomainNow}
              disabled={domainBusy || !(domain?.domain || domainInput)}
            >
              Verify
            </Button>
          </div>

          {domainError && (
            <p style={{ color: '#c0392b', fontSize: '13px', marginTop: '8px' }}>{domainError}</p>
          )}

          {domain?.domain && (
            <div className="card" style={{ marginTop: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <b>{domain.domain}</b>
                <span
                  className={`status ${domain.status === 'verified' ? '' : 'draft'}`}
                >
                  <span className="dot"></span>
                  {domain.status === 'verified' ? 'Verified' : 'Pending DNS'}
                </span>
              </div>

              <p className="muted" style={{ fontSize: '13px', margin: '10px 0 6px' }}>
                Add <b>both</b> records in your DNS provider, then press Verify. Either one alone is
                enough to prove ownership.
              </p>
              <pre
                style={{
                  background: '#f6f7fb',
                  padding: '12px',
                  borderRadius: '8px',
                  fontSize: '12.5px',
                  overflowX: 'auto',
                  whiteSpace: 'pre-wrap',
                }}
              >
{`1) Prove ownership
   Type: TXT
   Name: _brim-verify.${domain.domain}
   Value: ${domain.token || '(save the domain first)'}

2) Serve the chatbot
   Type: CNAME
   Name: ${domain.domain}
   Value: ${domain.app_host || 'your app hostname'}`}
              </pre>
              <p className="muted" style={{ fontSize: '12.5px' }}>
                The domain also has to be added as a custom domain in the hosting dashboard
                (Vercel → Project → Domains) so TLS is issued for it.
              </p>
            </div>
          )}
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

          <BotMetrics botId={bot.id} />

          <Card style={{ marginTop: '18px', textAlign: 'center', padding: '28px 20px' }}>
            <h3 style={{ fontSize: '15px', marginBottom: '6px' }}>Want more data to work with?</h3>
            <p className="muted" style={{ fontSize: '13px', marginBottom: '12px' }}>
              Open the bot and hold a few real conversations — metrics populate from those, never from samples.
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
