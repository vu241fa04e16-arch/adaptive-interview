/**
 * Input and File Validation Helpers
 */

/**
 * Validate email address format
 * @param {string} email 
 * @returns {boolean}
 */
export function validateEmail(email) {
  if (!email || typeof email !== 'string') return false;
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email.trim());
}

/**
 * Validate candidate profile form
 * @param {object} formData 
 * @returns {{ isValid: boolean, errors: object }}
 */
export function validateCandidateForm(formData) {
  const errors = {};

  if (!formData.name || !formData.name.trim()) {
    errors.name = 'Full name is required';
  } else if (formData.name.trim().length < 2) {
    errors.name = 'Name must be at least 2 characters';
  }

  if (!formData.email || !formData.email.trim()) {
    errors.email = 'Email address is required';
  } else if (!validateEmail(formData.email)) {
    errors.email = 'Please provide a valid email address';
  }

  if (!formData.targetRole || !formData.targetRole.trim()) {
    errors.targetRole = 'Target role/position is required';
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}

/**
 * Validate uploaded resume file
 * Allowed: PDF, DOCX, TXT. Max size: 10MB.
 * @param {File} file 
 * @returns {{ isValid: boolean, error?: string }}
 */
export function validateResumeFile(file) {
  if (!file) {
    return { isValid: false, error: 'Please select a resume file' };
  }

  const allowedExtensions = ['.pdf', '.docx', '.txt'];
  const name = file.name.toLowerCase();
  const hasValidExt = allowedExtensions.some(ext => name.endsWith(ext));

  if (!hasValidExt) {
    return {
      isValid: false,
      error: 'Invalid file format. Please upload a PDF, DOCX, or TXT file.',
    };
  }

  const maxSizeBytes = 10 * 1024 * 1024; // 10MB
  if (file.size > maxSizeBytes) {
    return {
      isValid: false,
      error: 'File size exceeds the 10MB maximum limit.',
    };
  }

  return { isValid: true };
}
