import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PREDEFINED_INDUSTRIES } from '../constants/industries';
import { projectService } from '../services/projectService';
import { botService } from '../services/botService';
import { knowledgeService } from '../services/knowledgeService';
import { useToast } from '../context/ToastContext';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { Select } from '../components/Select';
import { Card } from '../components/Card';

export const CreateBot = () => {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState('');
  const [createdBot, setCreatedBot] = useState(null);

  // Form State
  const [formData, setFormData] = useState({
    // Step 1: Basic Info
    name: 'Prycoons Property Assistant',
    industry: 'Real Estate',
    description: 'AI assistant for property discovery and customer enquiries.',
    companyName: 'Prycoons Real Estate',
    primaryUseCase: 'Customer Support',

    // Step 2: Knowledge Sources
    sampleDocKey: 'real_estate', // 'real_estate' | 'healthcare' | 'saas' | 'none'
    websiteUrl: '',
    instructions: 'Be polite, helpful, and answer property-related questions accurately based on the provided documents.',

    // Step 3: Bot Settings
    personality: 'Friendly & professional',
    language: 'English',
    welcomeMessage: 'Hi! How can I help you today with properties and real estate?',
    leadCollection: 'When relevant',
    humanHandoff: 'Allow when needed',
    responseStyle: 'Simple & clear',
  });

  const [uploadedFile, setUploadedFile] = useState(null);
  const [errors, setErrors] = useState({});

  const validateStep1 = () => {
    const errs = {};
    if (!formData.name.trim()) errs.name = 'Bot name is required.';
    if (!formData.industry) errs.industry = 'Please select an industry.';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleNext = () => {
    if (step === 1 && !validateStep1()) return;
    setStep((prev) => Math.min(prev + 1, 4));
  };

  const handleBack = () => {
    setStep((prev) => Math.max(prev - 1, 1));
  };

  const handleSubmit = async () => {
    setLoading(true);
    setApiError('');

    try {
      // 1. Create the project first
      const projectName = formData.companyName.trim() || `${formData.name} Project`;
      const project = await projectService.createProject({
        name: projectName,
        industry: formData.industry,
        description: formData.description,
      });

      // 2. Create the bot under this project
      const bot = await botService.createBot({
        project_id: project.id,
        name: formData.name.trim(),
        description: formData.description.trim(),
        language: formData.language,
        personality: formData.personality,
        welcome_message: formData.welcomeMessage.trim(),
        status: 'Live',
      });

      // 3. Attach knowledge sources selected in Step 2
      let attachedKnowledgeCount = 0;

      // 3a. Seed sample document if chosen
      if (formData.sampleDocKey && formData.sampleDocKey !== 'none') {
        try {
          await knowledgeService.seedSampleDocument(bot.id, formData.sampleDocKey);
          attachedKnowledgeCount++;
        } catch (seedErr) {
          console.warn('Could not seed sample doc:', seedErr);
        }
      }

      // 3b. Upload custom file if provided
      if (uploadedFile) {
        try {
          await knowledgeService.uploadFile(bot.id, uploadedFile);
          attachedKnowledgeCount++;
        } catch (uploadErr) {
          console.warn('Could not upload file:', uploadErr);
        }
      }

      // 3c. Add website if provided
      if (formData.websiteUrl.trim()) {
        try {
          await knowledgeService.addWebsite(bot.id, {
            url: formData.websiteUrl.trim(),
            name: `${formData.name} Website`,
          });
          attachedKnowledgeCount++;
        } catch (webErr) {
          console.warn('Could not index website:', webErr);
        }
      }

      // 3d. Add custom instructions if provided
      if (formData.instructions.trim()) {
        try {
          await knowledgeService.addInstruction(bot.id, {
            name: 'Core System Guidelines',
            instructions: formData.instructions.trim(),
            tone: formData.personality,
          });
          attachedKnowledgeCount++;
        } catch (instrErr) {
          console.warn('Could not save instructions:', instrErr);
        }
      }

      setCreatedBot(bot);
      setStep(5); // Success step
      showToast(
        attachedKnowledgeCount > 0
          ? `Bot created with ${attachedKnowledgeCount} knowledge source(s) indexed!`
          : 'Bot created successfully in PostgreSQL database!'
      );
    } catch (err) {
      setApiError(err.userMessage || 'Failed to create bot. Please check your inputs.');
    } finally {
      setLoading(false);
    }
  };

  const copyShareLink = () => {
    if (!createdBot) return;
    const shareUrl = `https://chat.brim.ai/${createdBot.shareable_slug}`;
    navigator.clipboard?.writeText(shareUrl);
    showToast('Shareable link copied to clipboard!');
  };

  const stepLabels = ['Basic information', 'Knowledge sources', 'Bot settings', 'Review'];

  // Success Screen (Step 5)
  if (step === 5 && createdBot) {
    const shareUrl = `https://chat.brim.ai/${createdBot.shareable_slug}`;
    return (
      <div className="login" style={{ background: 'var(--bg)', minHeight: 'calc(100vh - 120px)' }}>
        <div className="success">
          <div className="success-icon">✓</div>
          <h1 style={{ fontSize: '26px' }}>Bot created successfully</h1>
          <p className="muted" style={{ marginTop: '8px' }}>
            Your chatbot <b>{createdBot.name}</b> is saved in the database and ready for use.
          </p>

          <Card style={{ textAlign: 'left', marginTop: '28px' }}>
            <b style={{ fontSize: '14px' }}>Shareable chatbot link</b>
            <div className="link-box">
              <input readOnly value={shareUrl} />
              <Button variant="primary" onClick={copyShareLink}>
                Copy
              </Button>
            </div>
            <p className="muted" style={{ fontSize: '12px' }}>
              Public Slug: <code>{createdBot.shareable_slug}</code>
            </p>
          </Card>

          <div style={{ marginTop: '28px', display: 'flex', justifyContent: 'center', gap: '14px' }}>
            <Button variant="primary" onClick={() => navigate(`/bots/${createdBot.id}`)}>
              Open Bot Overview
            </Button>
            <Button variant="secondary" onClick={() => navigate('/dashboard')}>
              Go to Dashboard
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="wizard">
      <div className="page-head">
        <div>
          <h1>Create a new bot</h1>
          <p className="muted">Set up the basic information and personality for your assistant.</p>
        </div>
      </div>

      <div className="steps">
        {stepLabels.map((label, idx) => (
          <div key={label} className={`step ${step === idx + 1 ? 'active' : ''}`}>
            {idx + 1}. {label}
          </div>
        ))}
      </div>

      {apiError && (
        <div
          style={{
            background: '#fee2e2',
            border: '1px solid #fca5a5',
            color: '#b91c1c',
            padding: '12px 16px',
            borderRadius: '10px',
            marginBottom: '20px',
            fontSize: '13.5px',
          }}
        >
          {apiError}
        </div>
      )}

      <Card>
        {/* Step 1: Basic Information */}
        {step === 1 && (
          <div className="form-grid">
            <Input
              label="Bot name"
              required
              value={formData.name}
              error={errors.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g. Prycoons Property Assistant"
            />

            <Select
              label="Industry"
              required
              options={PREDEFINED_INDUSTRIES}
              value={formData.industry}
              error={errors.industry}
              onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
            />

            <div className="field span2">
              <label>Short description</label>
              <textarea
                rows="3"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Describe what your bot helps with..."
              />
            </div>

            <Input
              label="Business / Company name"
              value={formData.companyName}
              onChange={(e) => setFormData({ ...formData, companyName: e.target.value })}
              placeholder="e.g. Prycoons Real Estate"
            />

            <Select
              label="Primary use case"
              options={[
                'Customer Support',
                'Lead Generation',
                'Product Discovery',
                'Sales Assistance',
                'Information & FAQ',
              ]}
              value={formData.primaryUseCase}
              onChange={(e) => setFormData({ ...formData, primaryUseCase: e.target.value })}
            />
          </div>
        )}

        {/* Step 2: Knowledge Sources */}
        {step === 2 && (
          <div>
            <div className="notice" style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '12px 16px', borderRadius: '8px', marginBottom: '18px' }}>
              💡 <b>Knowledge Base Setup:</b> Choose a pre-packaged industry knowledge guide for immediate demo testing, or upload your own business document.
            </div>

            {/* Quick Demo Document Picker */}
            <div style={{ marginBottom: '20px', padding: '16px', background: '#fafbff', border: '1px solid var(--line)', borderRadius: '10px' }}>
              <b style={{ fontSize: '14.5px', color: 'var(--brand)', display: 'block', marginBottom: '4px' }}>
                ⚡ Pre-Packaged Demo Knowledge Guides (Recommended for Demo)
              </b>
              <p className="muted" style={{ fontSize: '13px', marginBottom: '12px' }}>
                Select a sample document to automatically seed into the bot's RAG knowledge base upon creation.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
                {[
                  { key: 'real_estate', title: '🏢 Real Estate Guide', desc: 'Prycoons Projects, Sunset Palms, 3/4 BHK' },
                  { key: 'healthcare', title: '🏥 Healthcare Guide', desc: 'Apex Medical, Dr. Rao, Cardiology, OPD' },
                  { key: 'saas', title: '☁️ SaaS Platform Docs', desc: 'CloudScale AI, Starter $49, Pro $199' },
                  { key: 'none', title: '🚫 None / Empty', desc: 'Start with blank knowledge base' },
                ].map((item) => (
                  <div
                    key={item.key}
                    onClick={() => setFormData({ ...formData, sampleDocKey: item.key })}
                    style={{
                      padding: '12px',
                      borderRadius: '8px',
                      border: formData.sampleDocKey === item.key ? '2px solid var(--brand)' : '1px solid var(--line)',
                      background: formData.sampleDocKey === item.key ? '#eff6ff' : '#fff',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <b style={{ fontSize: '13.5px', display: 'block', color: formData.sampleDocKey === item.key ? 'var(--brand)' : '#111827' }}>
                      {item.title}
                    </b>
                    <span className="muted" style={{ fontSize: '12px' }}>{item.desc}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
              <div className="card" style={{ padding: '16px', border: '1px solid var(--line)', borderRadius: '10px' }}>
                <b>📄 Upload Custom Document</b>
                <p className="muted" style={{ fontSize: '12.5px', margin: '4px 0 12px' }}>
                  Supported: .PDF, .DOCX, .TXT, .PNG, .JPG (Max 25MB)
                </p>
                <input
                  type="file"
                  id="bot-create-file-input"
                  accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.webp"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    if (e.target.files?.[0]) {
                      setUploadedFile(e.target.files[0]);
                      showToast(`Selected file: ${e.target.files[0].name}`);
                    }
                  }}
                />
                <Button
                  variant="secondary"
                  onClick={() => document.getElementById('bot-create-file-input')?.click()}
                >
                  {uploadedFile ? `📎 ${uploadedFile.name}` : '+ Choose File'}
                </Button>
                {uploadedFile && (
                  <button
                    onClick={() => setUploadedFile(null)}
                    style={{ marginLeft: '8px', background: 'none', border: 'none', color: '#dc2626', cursor: 'pointer', fontSize: '12px' }}
                  >
                    Remove
                  </button>
                )}
              </div>

              <div className="card" style={{ padding: '16px', border: '1px solid var(--line)', borderRadius: '10px' }}>
                <b>🌐 Website URL</b>
                <p className="muted" style={{ fontSize: '12.5px', margin: '4px 0 10px' }}>
                  Crawl website for answers (Optional)
                </p>
                <input
                  placeholder="https://example.com"
                  value={formData.websiteUrl}
                  onChange={(e) => setFormData({ ...formData, websiteUrl: e.target.value })}
                  style={{ width: '100%', padding: '9px 12px', border: '1px solid var(--line)', borderRadius: '8px', fontSize: '13px' }}
                />
              </div>

              <div className="card" style={{ gridColumn: 'span 2', padding: '16px', border: '1px solid var(--line)', borderRadius: '10px' }}>
                <b>✦ Custom Prompt Guidelines & Business Rules</b>
                <p className="muted" style={{ fontSize: '12.5px', margin: '4px 0 8px' }}>
                  Define specific rules, tone, and answering constraints for this bot.
                </p>
                <textarea
                  rows="3"
                  value={formData.instructions}
                  onChange={(e) => setFormData({ ...formData, instructions: e.target.value })}
                  placeholder="Be polite, helpful, and answer questions accurately based on the provided documents..."
                  style={{ width: '100%', padding: '10px 12px', border: '1px solid var(--line)', borderRadius: '8px', fontSize: '13px', lineHeight: '1.5' }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Bot Settings */}
        {step === 3 && (
          <div className="form-grid">
            <Select
              label="Bot personality"
              options={['Friendly & professional', 'Professional', 'Casual', 'Concise']}
              value={formData.personality}
              onChange={(e) => setFormData({ ...formData, personality: e.target.value })}
            />

            <Select
              label="Default language"
              options={['English', 'Hindi', 'Gujarati', 'Tamil', 'Spanish', 'French', 'German']}
              value={formData.language}
              onChange={(e) => setFormData({ ...formData, language: e.target.value })}
            />

            <div className="field span2">
              <label>Welcome message</label>
              <textarea
                rows="3"
                value={formData.welcomeMessage}
                onChange={(e) => setFormData({ ...formData, welcomeMessage: e.target.value })}
                placeholder="Greeting sent when a user opens the chat"
              />
            </div>

            <Select
              label="Lead collection"
              options={['When relevant', 'Always', 'Never']}
              value={formData.leadCollection}
              onChange={(e) => setFormData({ ...formData, leadCollection: e.target.value })}
            />

            <Select
              label="Human handoff"
              options={['Allow when needed', 'Always offer', 'Disabled']}
              value={formData.humanHandoff}
              onChange={(e) => setFormData({ ...formData, humanHandoff: e.target.value })}
            />

            <div className="field span2">
              <Select
                label="Response style"
                options={['Simple & clear', 'Detailed', 'Business professional']}
                value={formData.responseStyle}
                onChange={(e) => setFormData({ ...formData, responseStyle: e.target.value })}
              />
            </div>
          </div>
        )}

        {/* Step 4: Review */}
        {step === 4 && (
          <div>
            <h3 style={{ fontSize: '18px', marginBottom: '4px' }}>Review your bot</h3>
            <p className="muted">
              {formData.name} · {formData.industry}
            </p>

            <hr style={{ border: 0, borderTop: '1px solid var(--line)', margin: '20px 0' }} />

            <div style={{ display: 'grid', gap: '12px', fontSize: '14px', lineHeight: '1.6' }}>
              <p>
                <b>Bot Name:</b> {formData.name}
              </p>
              <p>
                <b>Industry:</b> {formData.industry}
              </p>
              <p>
                <b>Company / Project:</b> {formData.companyName || 'Default'}
              </p>
              <p>
                <b>Description:</b> {formData.description || 'None provided'}
              </p>
              <p>
                <b>Language & Personality:</b> {formData.language} · {formData.personality}
              </p>
              <p>
                <b>Welcome Message:</b> "{formData.welcomeMessage}"
              </p>
              <p>
                <b>Lead Capture:</b> {formData.leadCollection}
              </p>
            </div>
          </div>
        )}

        {/* Wizard Footer Actions */}
        <div className="wizard-actions">
          <Button variant="secondary" onClick={step > 1 ? handleBack : () => navigate('/dashboard')}>
            {step === 1 ? 'Cancel' : 'Back'}
          </Button>

          {step < 4 ? (
            <Button variant="primary" onClick={handleNext}>
              Continue
            </Button>
          ) : (
            <Button variant="primary" loading={loading} onClick={handleSubmit}>
              Create Bot
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
};
