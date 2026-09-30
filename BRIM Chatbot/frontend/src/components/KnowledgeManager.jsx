import React, { useState, useEffect, useRef } from 'react';
import { knowledgeService } from '../services/knowledgeService';
import { useToast } from '../context/ToastContext';
import { Button } from './Button';
import { Input } from './Input';
import { Select } from './Select';
import { Card } from './Card';
import { LoadingState } from './LoadingState';
import { EmptyState } from './EmptyState';
import { ErrorState } from './ErrorState';
import { Modal } from './Modal';

export const KnowledgeManager = ({ botId, onSourcesChange }) => {
  const { showToast } = useToast();
  const fileInputRef = useRef(null);

  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [subTab, setSubTab] = useState('files'); // 'files' | 'websites' | 'social' | 'instructions'

  // Action Loading states
  const [uploading, setUploading] = useState(false);
  const [submittingWebsite, setSubmittingWebsite] = useState(false);
  const [submittingSocial, setSubmittingSocial] = useState(false);
  const [submittingInstruction, setSubmittingInstruction] = useState(false);

  // Forms State
  const [websiteForm, setWebsiteForm] = useState({ url: '', name: '' });
  const [socialForm, setSocialForm] = useState({ url: '', platform: 'LinkedIn', name: '' });
  const [instructionForm, setInstructionForm] = useState({
    name: 'Primary Business Guidelines',
    instructions: '',
    tone: 'Friendly & professional',
    restrictions: '',
    objectives: '',
  });

  // Preview Modal State
  const [selectedSource, setSelectedSource] = useState(null);

  const fetchSources = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await knowledgeService.getBotKnowledge(botId);
      setSources(data || []);
      if (onSourcesChange) onSourcesChange(data || []);
    } catch (err) {
      setError(err.userMessage || 'Failed to load knowledge sources.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (botId) {
      fetchSources();
    }
  }, [botId]);

  // File Upload Handler
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Check size (< 25MB)
    if (file.size > 25 * 1024 * 1024) {
      showToast('File size exceeds the 25MB maximum limit.');
      return;
    }

    setUploading(true);
    try {
      await knowledgeService.uploadFile(botId, file);
      showToast(`Uploaded and processed "${file.name}"!`);
      if (fileInputRef.current) fileInputRef.current.value = '';
      await fetchSources();
    } catch (err) {
      showToast(err.userMessage || 'Failed to upload file.');
    } finally {
      setUploading(false);
    }
  };

  // Add Website Handler
  const handleAddWebsite = async (e) => {
    e.preventDefault();
    if (!websiteForm.url.trim()) {
      showToast('Please enter a valid website URL.');
      return;
    }

    setSubmittingWebsite(true);
    try {
      await knowledgeService.addWebsite(botId, websiteForm);
      showToast('Website fetched and indexed successfully!');
      setWebsiteForm({ url: '', name: '' });
      await fetchSources();
    } catch (err) {
      showToast(err.userMessage || 'Failed to scrape website.');
    } finally {
      setSubmittingWebsite(false);
    }
  };

  // Add Social Link Handler
  const handleAddSocial = async (e) => {
    e.preventDefault();
    if (!socialForm.url.trim()) {
      showToast('Please enter a social profile URL.');
      return;
    }

    setSubmittingSocial(true);
    try {
      await knowledgeService.addSocialLink(botId, socialForm);
      showToast('Social profile link recorded!');
      setSocialForm({ url: '', platform: 'LinkedIn', name: '' });
      await fetchSources();
    } catch (err) {
      showToast(err.userMessage || 'Failed to add social link.');
    } finally {
      setSubmittingSocial(false);
    }
  };

  // Add Instructions Handler
  const handleAddInstruction = async (e) => {
    e.preventDefault();
    if (!instructionForm.instructions.trim()) {
      showToast('Please enter the primary guidance or instructions.');
      return;
    }

    setSubmittingInstruction(true);
    try {
      await knowledgeService.addInstruction(botId, instructionForm);
      showToast('Custom instructions and prompt rules saved!');
      setInstructionForm({
        name: 'Primary Business Guidelines',
        instructions: '',
        tone: 'Friendly & professional',
        restrictions: '',
        objectives: '',
      });
      await fetchSources();
    } catch (err) {
      showToast(err.userMessage || 'Failed to save instructions.');
    } finally {
      setSubmittingInstruction(false);
    }
  };

  // Delete Source Handler
  const handleDeleteSource = async (sourceId, sourceName) => {
    if (!window.confirm(`Are you sure you want to delete "${sourceName}"?`)) return;

    try {
      await knowledgeService.deleteKnowledgeSource(sourceId);
      showToast('Knowledge source removed.');
      await fetchSources();
    } catch (err) {
      showToast(err.userMessage || 'Failed to delete knowledge source.');
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Filter sources by active tab
  const filesList = sources.filter((s) => s.source_type === 'DOCUMENT' || s.source_type === 'IMAGE');
  const websitesList = sources.filter((s) => s.source_type === 'WEBSITE');
  const socialList = sources.filter((s) => s.source_type === 'SOCIAL_LINK');
  const instructionsList = sources.filter((s) => s.source_type === 'INSTRUCTION');

  return (
    <div>
      {/* Sub-navigation tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
        <button
          className={`btn ${subTab === 'files' ? 'primary' : 'secondary'}`}
          onClick={() => setSubTab('files')}
        >
          📄 Files & Documents ({filesList.length})
        </button>
        <button
          className={`btn ${subTab === 'websites' ? 'primary' : 'secondary'}`}
          onClick={() => setSubTab('websites')}
        >
          🌐 Websites ({websitesList.length})
        </button>
        <button
          className={`btn ${subTab === 'social' ? 'primary' : 'secondary'}`}
          onClick={() => setSubTab('social')}
        >
          🔗 Social Profiles ({socialList.length})
        </button>
        <button
          className={`btn ${subTab === 'instructions' ? 'primary' : 'secondary'}`}
          onClick={() => setSubTab('instructions')}
        >
          ✦ Custom Instructions ({instructionsList.length})
        </button>
      </div>

      {loading ? (
        <LoadingState message="Loading knowledge base..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchSources} />
      ) : (
        <div>
          {/* FILES & DOCUMENTS SECTION */}
          {subTab === 'files' && (
            <div className="grid" style={{ gridTemplateColumns: '1.2fr 0.8fr' }}>
              <Card>
                <div className="page-head" style={{ marginBottom: '16px' }}>
                  <div>
                    <h3 style={{ margin: 0 }}>Documents & Images</h3>
                    <p className="muted" style={{ fontSize: '13px' }}>
                      Upload PDFs, Word documents, text files, or property/product images.
                    </p>
                  </div>
                </div>

                {filesList.length === 0 ? (
                  <EmptyState
                    icon="📄"
                    title="No files uploaded yet"
                    description="Upload business catalogs, brochures, FAQs, or rate cards."
                  />
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {filesList.map((item) => (
                      <div
                        key={item.id}
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
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div
                            style={{
                              width: '38px',
                              height: '38px',
                              borderRadius: '8px',
                              background: item.source_type === 'IMAGE' ? '#e0f7fa' : 'var(--soft)',
                              color: 'var(--brand)',
                              display: 'grid',
                              placeItems: 'center',
                              fontSize: '16px',
                            }}
                          >
                            {item.source_type === 'IMAGE' ? '🖼' : '📄'}
                          </div>
                          <div>
                            <b style={{ fontSize: '14px', display: 'block' }}>{item.name}</b>
                            <span className="muted" style={{ fontSize: '12px' }}>
                              {formatFileSize(item.file_size)} · {item.chunks_count} chunks extracted
                            </span>
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span
                            className={`status ${
                              item.processing_status === 'COMPLETED'
                                ? ''
                                : item.processing_status === 'FAILED'
                                ? 'status-failed'
                                : 'draft'
                            }`}
                            style={
                              item.processing_status === 'FAILED'
                                ? { background: '#fee2e2', color: '#b91c1c' }
                                : {}
                            }
                          >
                            <span className="dot"></span>
                            {item.processing_status}
                          </span>

                          <button
                            className="btn secondary"
                            style={{ padding: '6px 10px', fontSize: '12px' }}
                            onClick={() => setSelectedSource(item)}
                          >
                            Inspect
                          </button>

                          <button
                            className="btn danger-btn"
                            style={{ padding: '6px 10px', fontSize: '12px' }}
                            onClick={() => handleDeleteSource(item.id, item.name)}
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Upload Dropzone Card */}
              <Card>
                <h3 style={{ marginBottom: '6px' }}>Upload New File</h3>
                <p className="muted" style={{ fontSize: '13px', marginBottom: '18px' }}>
                  Supported formats: <b>.PDF, .DOC, .DOCX, .TXT, .PNG, .JPG, .WEBP</b> (Max 25MB)
                </p>

                <div
                  style={{
                    border: '2px dashed var(--line)',
                    borderRadius: '12px',
                    padding: '36px 20px',
                    textAlign: 'center',
                    background: '#fafbff',
                    cursor: 'pointer',
                  }}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    style={{ display: 'none' }}
                    accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.webp"
                    onChange={handleFileUpload}
                  />
                  <div style={{ fontSize: '32px', marginBottom: '8px' }}>📁</div>
                  <b style={{ fontSize: '14px', color: 'var(--brand)' }}>Click to browse file</b>
                  <p className="muted" style={{ fontSize: '12px', marginTop: '4px' }}>
                    Files are parsed, validated, and chunked automatically.
                  </p>
                </div>

                <div style={{ marginTop: '18px' }}>
                  <Button
                    variant="primary"
                    full
                    loading={uploading}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Select File to Upload
                  </Button>
                </div>
              </Card>
            </div>
          )}

          {/* WEBSITES SECTION */}
          {subTab === 'websites' && (
            <div className="grid" style={{ gridTemplateColumns: '1.2fr 0.8fr' }}>
              <Card>
                <div className="page-head" style={{ marginBottom: '16px' }}>
                  <div>
                    <h3 style={{ margin: 0 }}>Indexed Websites</h3>
                    <p className="muted" style={{ fontSize: '13px' }}>
                      Webpages crawled and extracted for chatbot knowledge.
                    </p>
                  </div>
                </div>

                {websitesList.length === 0 ? (
                  <EmptyState
                    icon="🌐"
                    title="No websites linked yet"
                    description="Enter your public website or documentation URL to index text."
                  />
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {websitesList.map((item) => (
                      <div
                        key={item.id}
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
                          <b style={{ fontSize: '14px', display: 'block' }}>{item.name}</b>
                          <a
                            href={item.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="muted"
                            style={{ fontSize: '12px', textDecoration: 'underline' }}
                          >
                            {item.source_url}
                          </a>
                          <span className="muted" style={{ fontSize: '12px', display: 'block', marginTop: '2px' }}>
                            {item.chunks_count} text chunks extracted
                          </span>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span className="status">
                            <span className="dot"></span>
                            {item.processing_status}
                          </span>
                          <button
                            className="btn secondary"
                            style={{ padding: '6px 10px', fontSize: '12px' }}
                            onClick={() => setSelectedSource(item)}
                          >
                            Inspect
                          </button>
                          <button
                            className="btn danger-btn"
                            style={{ padding: '6px 10px', fontSize: '12px' }}
                            onClick={() => handleDeleteSource(item.id, item.name)}
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Add Website Form */}
              <Card>
                <h3 style={{ marginBottom: '6px' }}>Add Website URL</h3>
                <p className="muted" style={{ fontSize: '13px', marginBottom: '18px' }}>
                  The engine will fetch the page, strip HTML navigation tags, and extract clean business text.
                </p>

                <form onSubmit={handleAddWebsite}>
                  <Input
                    label="Page or Site URL"
                    required
                    placeholder="https://example.com/about"
                    value={websiteForm.url}
                    onChange={(e) => setWebsiteForm({ ...websiteForm, url: e.target.value })}
                  />

                  <Input
                    label="Custom Label / Name (Optional)"
                    placeholder="e.g. About Us Page"
                    value={websiteForm.name}
                    onChange={(e) => setWebsiteForm({ ...websiteForm, name: e.target.value })}
                  />

                  <div style={{ marginTop: '16px' }}>
                    <Button type="submit" variant="primary" full loading={submittingWebsite}>
                      Fetch & Ingest Website
                    </Button>
                  </div>
                </form>
              </Card>
            </div>
          )}

          {/* SOCIAL LINKS SECTION */}
          {subTab === 'social' && (
            <div className="grid" style={{ gridTemplateColumns: '1.2fr 0.8fr' }}>
              <Card>
                <div className="page-head" style={{ marginBottom: '16px' }}>
                  <div>
                    <h3 style={{ margin: 0 }}>Social Media Profiles</h3>
                    <p className="muted" style={{ fontSize: '13px' }}>
                      Company social channels configured for audience engagement and future automated posts sync.
                    </p>
                  </div>
                </div>

                {socialList.length === 0 ? (
                  <EmptyState
                    icon="🔗"
                    title="No social links configured"
                    description="Link your LinkedIn, X (Twitter), Instagram, YouTube, or GitHub profiles."
                  />
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {socialList.map((item) => (
                      <div
                        key={item.id}
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
                          <b style={{ fontSize: '14px', display: 'block' }}>{item.name}</b>
                          <a
                            href={item.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="muted"
                            style={{ fontSize: '12px' }}
                          >
                            {item.source_url}
                          </a>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span className="status">
                            <span className="dot"></span>
                            Tracked
                          </span>
                          <button
                            className="btn danger-btn"
                            style={{ padding: '6px 10px', fontSize: '12px' }}
                            onClick={() => handleDeleteSource(item.id, item.name)}
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Add Social Link Form */}
              <Card>
                <h3 style={{ marginBottom: '6px' }}>Link Social Profile</h3>
                <p className="muted" style={{ fontSize: '13px', marginBottom: '18px' }}>
                  Store and link verified company social profiles.
                </p>

                <form onSubmit={handleAddSocial}>
                  <Select
                    label="Platform"
                    options={['LinkedIn', 'X (Twitter)', 'Instagram', 'Facebook', 'YouTube', 'GitHub', 'Other']}
                    value={socialForm.platform}
                    onChange={(e) => setSocialForm({ ...socialForm, platform: e.target.value })}
                  />

                  <Input
                    label="Profile URL"
                    required
                    placeholder="https://linkedin.com/company/yourbusiness"
                    value={socialForm.url}
                    onChange={(e) => setSocialForm({ ...socialForm, url: e.target.value })}
                  />

                  <Input
                    label="Display Label (Optional)"
                    placeholder="e.g. Official LinkedIn"
                    value={socialForm.name}
                    onChange={(e) => setSocialForm({ ...socialForm, name: e.target.value })}
                  />

                  <div style={{ marginTop: '16px' }}>
                    <Button type="submit" variant="primary" full loading={submittingSocial}>
                      Save Social Profile
                    </Button>
                  </div>
                </form>
              </Card>
            </div>
          )}

          {/* CUSTOM INSTRUCTIONS SECTION */}
          {subTab === 'instructions' && (
            <div className="grid" style={{ gridTemplateColumns: '1.2fr 0.8fr' }}>
              <Card>
                <div className="page-head" style={{ marginBottom: '16px' }}>
                  <div>
                    <h3 style={{ margin: 0 }}>Custom Prompt Guidelines</h3>
                    <p className="muted" style={{ fontSize: '13px' }}>
                      Explicit business instructions, tone rules, objectives, and restrictions.
                    </p>
                  </div>
                </div>

                {instructionsList.length === 0 ? (
                  <EmptyState
                    icon="✦"
                    title="No custom instructions added"
                    description="Define core business rules, answers to common scenarios, and boundaries."
                  />
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {instructionsList.map((item) => (
                      <div
                        key={item.id}
                        style={{
                          padding: '16px',
                          border: '1px solid var(--line)',
                          borderRadius: '12px',
                          background: '#fff',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                          <b style={{ fontSize: '15px' }}>{item.name}</b>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <button
                              className="btn secondary"
                              style={{ padding: '4px 8px', fontSize: '12px' }}
                              onClick={() => setSelectedSource(item)}
                            >
                              View Full Rules
                            </button>
                            <button
                              className="btn danger-btn"
                              style={{ padding: '4px 8px', fontSize: '12px' }}
                              onClick={() => handleDeleteSource(item.id, item.name)}
                            >
                              ✕
                            </button>
                          </div>
                        </div>

                        <div
                          style={{
                            background: '#fafbff',
                            padding: '12px',
                            borderRadius: '8px',
                            fontSize: '13px',
                            color: '#444957',
                            whiteSpace: 'pre-wrap',
                            maxHeight: '120px',
                            overflowY: 'auto',
                          }}
                        >
                          {item.extracted_text}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Add Instruction Form */}
              <Card>
                <h3 style={{ marginBottom: '6px' }}>Configure Guidelines</h3>
                <p className="muted" style={{ fontSize: '13px', marginBottom: '18px' }}>
                  Inject high-priority business guidance into your bot's knowledge layer.
                </p>

                <form onSubmit={handleAddInstruction}>
                  <Input
                    label="Instruction Title"
                    required
                    value={instructionForm.name}
                    onChange={(e) => setInstructionForm({ ...instructionForm, name: e.target.value })}
                  />

                  <div className="field">
                    <label>Core Instructions & Guidance *</label>
                    <textarea
                      rows="3"
                      required
                      placeholder="e.g. Always ask for customer's preferred budget before recommending properties..."
                      value={instructionForm.instructions}
                      onChange={(e) => setInstructionForm({ ...instructionForm, instructions: e.target.value })}
                    />
                  </div>

                  <Select
                    label="Response Tone"
                    options={['Friendly & professional', 'Formal & authoritative', 'Casual & helpful', 'Concise & direct']}
                    value={instructionForm.tone}
                    onChange={(e) => setInstructionForm({ ...instructionForm, tone: e.target.value })}
                  />

                  <div className="field">
                    <label>Restrictions & Boundaries (Optional)</label>
                    <textarea
                      rows="2"
                      placeholder="e.g. Do not quote unauthorized discounts or share internal employee phone numbers."
                      value={instructionForm.restrictions}
                      onChange={(e) => setInstructionForm({ ...instructionForm, restrictions: e.target.value })}
                    />
                  </div>

                  <div className="field">
                    <label>Conversation Objectives (Optional)</label>
                    <input
                      placeholder="e.g. Collect lead email and phone number for site visit"
                      value={instructionForm.objectives}
                      onChange={(e) => setInstructionForm({ ...instructionForm, objectives: e.target.value })}
                    />
                  </div>

                  <div style={{ marginTop: '16px' }}>
                    <Button type="submit" variant="primary" full loading={submittingInstruction}>
                      Save Custom Instruction
                    </Button>
                  </div>
                </form>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* Inspect Knowledge Modal */}
      <Modal
        isOpen={!!selectedSource}
        onClose={() => setSelectedSource(null)}
        title={selectedSource?.name || 'Knowledge Source Details'}
        maxWidth="640px"
      >
        {selectedSource && (
          <div>
            <div style={{ display: 'grid', gap: '8px', fontSize: '13.5px', marginBottom: '18px' }}>
              <p>
                <b>Type:</b> {selectedSource.source_type}
              </p>
              <p>
                <b>Status:</b>{' '}
                <span className="status">
                  <span className="dot"></span>
                  {selectedSource.processing_status}
                </span>
              </p>
              <p>
                <b>Chunks Generated:</b> {selectedSource.chunks_count}
              </p>
              {selectedSource.file_size && (
                <p>
                  <b>File Size:</b> {formatFileSize(selectedSource.file_size)}
                </p>
              )}
              {selectedSource.source_url && (
                <p>
                  <b>Source URL:</b>{' '}
                  <a href={selectedSource.source_url} target="_blank" rel="noreferrer">
                    {selectedSource.source_url}
                  </a>
                </p>
              )}
            </div>

            <h4 style={{ fontSize: '14px', marginBottom: '6px' }}>Extracted Text & Metadata</h4>
            <div
              style={{
                background: '#f8f9fc',
                border: '1px solid var(--line)',
                borderRadius: '8px',
                padding: '14px',
                fontSize: '12.5px',
                lineHeight: '1.6',
                maxHeight: '260px',
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
                fontFamily: 'monospace',
              }}
            >
              {selectedSource.extracted_text || 'No extracted text available.'}
            </div>

            <div style={{ marginTop: '20px', textAlign: 'right' }}>
              <Button variant="secondary" onClick={() => setSelectedSource(null)}>
                Close
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};
