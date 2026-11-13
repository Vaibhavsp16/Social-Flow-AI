const VISITOR_KEY = 'brim_visitor_id';

/**
 * A stable identity for this browser.
 *
 * The API distinguishes a chat (`session_id`) from a person (`visitor_id`). Analytics counted
 * sessions as users, so one person opening three chats looked like three customers. Everything in
 * the chat now sends this id, which is why unique-user numbers are real.
 */
export function getVisitorId() {
  try {
    let id = localStorage.getItem(VISITOR_KEY);
    if (!id) {
      id =
        (typeof crypto !== 'undefined' && crypto.randomUUID && crypto.randomUUID()) ||
        `v-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem(VISITOR_KEY, id);
    }
    return id;
  } catch {
    // Private mode / blocked storage: a per-page identity still beats none.
    return `v-temp-${Math.random().toString(36).slice(2, 10)}`;
  }
}

/** Timezone name and UTC offset, used to resolve "Tuesday 6pm" in the visitor's own clock. */
export function getTimeContext() {
  const now = new Date();
  let timezone = null;
  try {
    timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    timezone = null;
  }
  return {
    timezone,
    utc_offset_minutes: -now.getTimezoneOffset(),
    local_hour: now.getHours(),
  };
}
