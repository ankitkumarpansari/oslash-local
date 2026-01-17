/**
 * Query Parser for scoped searches
 * 
 * Supports syntax like:
 * - o/gmail/search terms
 * - o/drive/file name
 * - o/hubspot/company name
 * - o/slack/message content
 * - o/notion/page name
 */

export type ParsedQuery = {
  source: string | null;  // 'gmail', 'gdrive', 'gcal', 'hubspot', 'slack', 'notion', or null for all
  query: string;          // The actual search query
};

const SOURCE_ALIASES: Record<string, string> = {
  'gmail': 'gmail',
  'mail': 'gmail',
  'email': 'gmail',
  'drive': 'gdrive',
  'gdrive': 'gdrive',
  'docs': 'gdrive',
  'calendar': 'gcal',
  'gcal': 'gcal',
  'cal': 'gcal',
  'events': 'gcal',
  'meetings': 'gcal',
  'people': 'gpeople',
  'gpeople': 'gpeople',
  'contacts': 'gpeople',
  'directory': 'gpeople',
  'employees': 'gpeople',
  'coworkers': 'gpeople',
  'hubspot': 'hubspot',
  'crm': 'hubspot',
  'slack': 'slack',
  'messages': 'slack',
  'notion': 'notion',
  'pages': 'notion',
  'wiki': 'notion',
  'browser': 'browser',
  'history': 'browser',
  'bookmarks': 'browser',
  'chrome': 'browser',
  'visited': 'browser',
};

/**
 * Parse a query string to extract source filter and search query.
 * 
 * Supports formats:
 * - o/gmail/search terms
 * - o/drive/file name
 * - o/hubspot/company name
 * - o/slack/message content
 * - just search terms (no filter)
 */
export function parseQuery(input: string): ParsedQuery {
  const trimmed = input.trim();
  
  // Match pattern: o/source/query or o/source query
  const match = trimmed.match(/^o\/(\w+)[\/\s]+(.+)$/i);
  
  if (match) {
    const [, sourceKey, query] = match;
    const normalizedSource = SOURCE_ALIASES[sourceKey.toLowerCase()];
    
    if (normalizedSource) {
      return {
        source: normalizedSource,
        query: query.trim(),
      };
    }
  }
  
  // No special syntax, search all sources
  return {
    source: null,
    query: trimmed,
  };
}

/**
 * Get display name for a source
 */
export function getSourceDisplayName(source: string): string {
  const names: Record<string, string> = {
    gmail: 'Gmail',
    gdrive: 'Google Drive',
    gcal: 'Google Calendar',
    gpeople: 'Google People',
    hubspot: 'HubSpot',
    slack: 'Slack',
    notion: 'Notion',
    browser: 'Browser',
  };
  return names[source] || source;
}

