/**
 * String, numeric, and date formatting utilities
 */

/**
 * Format remaining seconds into MM:SS format
 * @param {number} totalSeconds 
 * @returns {string} e.g. "01:45"
 */
export function formatTime(totalSeconds) {
  if (typeof totalSeconds !== 'number' || totalSeconds < 0 || isNaN(totalSeconds)) {
    return '00:00';
  }
  const mins = Math.floor(totalSeconds / 60);
  const secs = Math.floor(totalSeconds % 60);
  const pad = (n) => n.toString().padStart(2, '0');
  return `${pad(mins)}:${pad(secs)}`;
}

/**
 * Format score into display percentage
 * @param {number} score - numeric score between 0-100 or 0-1
 * @returns {string} e.g. "88%"
 */
export function formatScore(score) {
  if (score === undefined || score === null || isNaN(score)) return '0%';
  const normalized = score > 1 ? score : score * 100;
  return `${Math.round(normalized)}%`;
}

/**
 * Format ISO string into readable date and time
 * @param {string|Date} dateInput 
 * @returns {string} e.g. "Oct 10, 2026, 8:45 PM"
 */
export function formatTimestamp(dateInput) {
  if (!dateInput) return 'N/A';
  try {
    const d = new Date(dateInput);
    if (isNaN(d.getTime())) return 'Invalid date';
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return String(dateInput);
  }
}

/**
 * Format short relative timestamp
 * @param {string|Date} dateInput 
 * @returns {string} e.g. "2 min ago"
 */
export function formatRelativeTime(dateInput) {
  if (!dateInput) return '';
  const now = Date.now();
  const past = new Date(dateInput).getTime();
  const diffSec = Math.floor((now - past) / 1000);

  if (diffSec < 60) return `${Math.max(1, diffSec)}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  return `${diffHr}h ago`;
}

/**
 * Truncate text with ellipsis
 * @param {string} text 
 * @param {number} maxLen 
 * @returns {string}
 */
export function truncateText(text, maxLen = 60) {
  if (!text) return '';
  if (text.length <= maxLen) return text;
  return `${text.substring(0, maxLen)}...`;
}

/**
 * Format byte count into human-readable size
 * @param {number} bytes 
 * @returns {string} e.g. "2.4 MB"
 */
export function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
