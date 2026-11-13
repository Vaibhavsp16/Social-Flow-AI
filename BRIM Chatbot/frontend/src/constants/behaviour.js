/**
 * The wizard speaks in human labels ("Lead Generation"); the API stores stable keys
 * ("lead_generation"). Without this mapping the settings were collected and then dropped on the
 * floor, which is why every bot behaved the same regardless of what was chosen.
 */

export const USE_CASE_OPTIONS = [
  { value: 'customer_support', label: 'Customer Support' },
  { value: 'lead_generation', label: 'Lead Generation' },
  { value: 'appointment_booking', label: 'Appointment Booking' },
  { value: 'product_information', label: 'Product Discovery' },
  { value: 'advisory', label: 'Sales Advisory' },
  // No separate FAQ playbook: a FAQ bot is a general assistant that happens to have documents.
  { value: 'general_assistant', label: 'Information & FAQ' },
  { value: 'internal_knowledge', label: 'Internal Knowledge' },
  { value: 'education_admissions', label: 'Education & Admissions' },
  { value: 'general_assistant', label: 'General Assistant' },
];

// Labels the wizard used before the key map existed, kept so old drafts still resolve.
const LEGACY_USE_CASE_LABELS = {
  'product discovery': 'product_information',
  'sales assistance': 'advisory',
  'information & faq': 'general_assistant',
};

export const RESPONSE_STYLE_OPTIONS = [
  { value: 'simple_clear', label: 'Simple & clear' },
  { value: 'detailed', label: 'Detailed' },
  { value: 'business_professional', label: 'Business professional' },
  { value: 'concise', label: 'Concise' },
  { value: 'warm_conversational', label: 'Warm & conversational' },
];

export const LEAD_COLLECTION_OPTIONS = [
  { value: 'when_relevant', label: 'When relevant' },
  { value: 'always', label: 'Always' },
  { value: 'never', label: 'Never' },
];

export const HANDOFF_OPTIONS = [
  { value: 'allow_when_needed', label: 'Allow when needed' },
  { value: 'always_offer', label: 'Always offer' },
  { value: 'disabled', label: 'Disabled' },
];

export const PERSONALITY_OPTIONS = [
  'Friendly & professional',
  'Warm & conversational',
  'Concise & efficient',
  'Formal & corporate',
  'Enthusiastic sales',
];

export function useCaseToKey(value) {
  if (!value) return 'general_assistant';
  const match = USE_CASE_OPTIONS.find(
    (option) => option.value === value || option.label.toLowerCase() === String(value).toLowerCase()
  );
  if (match) return match.value;
  return LEGACY_USE_CASE_LABELS[String(value).toLowerCase()] || 'general_assistant';
}

function labelToKey(options, value, fallback) {
  if (!value) return fallback;
  const match = options.find(
    (option) => option.value === value || option.label.toLowerCase() === String(value).toLowerCase()
  );
  return match ? match.value : fallback;
}

export const styleToKey = (value) => labelToKey(RESPONSE_STYLE_OPTIONS, value, 'simple_clear');
export const leadPolicyToKey = (value) => labelToKey(LEAD_COLLECTION_OPTIONS, value, 'when_relevant');
export const handoffToKey = (value) => labelToKey(HANDOFF_OPTIONS, value, 'allow_when_needed');

export function keyToLabel(options, key, fallback) {
  const match = options.find((option) => option.value === key);
  return match ? match.label : fallback;
}
