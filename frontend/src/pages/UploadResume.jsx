import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileText,
  User,
  Mail,
  Briefcase,
  CheckCircle2,
  Sparkles,
  ArrowRight,
  AlertCircle,
  X,
} from 'lucide-react';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import Spinner from '../components/common/Spinner';
import { createSession, uploadResume } from '../services/api';
import { validateCandidateForm, validateResumeFile } from '../utils/validators';
import { formatFileSize } from '../utils/formatters';

/**
 * UploadResume Page
 * Collects candidate metadata and parses resume file to bootstrap adaptive interview.
 */
export default function UploadResume() {
  const navigate = useNavigate();

  // Form states
  const [formData, setFormData] = useState({
    name: 'Sarah Connor',
    email: 'sarah.connor@cyberdyne.io',
    targetRole: 'Senior Distributed Systems Architect',
  });
  const [resumeFile, setResumeFile] = useState(null);
  const [formErrors, setFormErrors] = useState({});

  // Workflow states
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [parsingProgress, setParsingProgress] = useState(null); // 'creating' | 'parsing' | 'done'
  const [parsedData, setParsedData] = useState(null);
  const [createdSessionId, setCreatedSessionId] = useState(null);
  const [error, setError] = useState(null);

  // File drag & drop state
  const [isDragging, setIsDragging] = useState(false);

  const handleInputChange = (field, val) => {
    setFormData((prev) => ({ ...prev, [field]: val }));
    if (formErrors[field]) {
      setFormErrors((prev) => ({ ...prev, [field]: null }));
    }
  };

  const handleFileSelect = (file) => {
    setError(null);
    const validation = validateResumeFile(file);
    if (!validation.isValid) {
      setError(validation.error);
      return;
    }
    setResumeFile(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    // Validate metadata
    const valResult = validateCandidateForm(formData);
    if (!valResult.isValid) {
      setFormErrors(valResult.errors);
      return;
    }

    if (!resumeFile) {
      setError('Please upload a resume file (PDF, DOCX, or TXT) to proceed.');
      return;
    }

    setIsSubmitting(true);
    try {
      // 1. Create Session: POST /sessions
      setParsingProgress('creating');
      const sessionResult = await createSession(formData);
      const newSessionId = sessionResult.sessionId;
      setCreatedSessionId(newSessionId);

      // 2. Upload and Parse Resume: POST /sessions/{id}/resume
      setParsingProgress('parsing');
      const resumeResult = await uploadResume(newSessionId, resumeFile);

      setParsedData(resumeResult);
      setParsingProgress('done');
    } catch (err) {
      console.error('Session creation / resume parsing error:', err);
      setError(err.message || 'Failed to process resume. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStartInterview = () => {
    if (createdSessionId) {
      navigate(`/interview/${createdSessionId}`);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <div className="text-center mb-8">
        <span className="px-3 py-1 rounded-full text-xs font-mono font-semibold bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
          Step 1 of 2: Candidate Intake
        </span>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white font-display mt-3">
          Candidate & Resume Intake
        </h1>
        <p className="text-sm text-slate-400 max-w-lg mx-auto mt-2">
          Initialize interview session parameters and extract domain proficiencies for tailored adaptive questioning.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-8">
        {!parsedData ? (
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Candidate Metadata Inputs */}
            <Card
              title="Candidate Information"
              subtitle="Used for session identification and recruiter reporting"
              icon={<User className="w-5 h-5 text-cyan-400" />}
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Full Name */}
                <div>
                  <label className="block text-xs font-medium text-slate-300 uppercase tracking-wider font-mono mb-1.5">
                    Full Name *
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => handleInputChange('name', e.target.value)}
                      placeholder="e.g. Alex Chen"
                      className="w-full bg-slate-900/80 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white focus:outline-none focus:border-cyan-500 transition-colors"
                    />
                  </div>
                  {formErrors.name && (
                    <p className="text-xs text-rose-400 mt-1">{formErrors.name}</p>
                  )}
                </div>

                {/* Email Address */}
                <div>
                  <label className="block text-xs font-medium text-slate-300 uppercase tracking-wider font-mono mb-1.5">
                    Email Address *
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => handleInputChange('email', e.target.value)}
                      placeholder="e.g. alex.chen@example.com"
                      className="w-full bg-slate-900/80 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white focus:outline-none focus:border-cyan-500 transition-colors"
                    />
                  </div>
                  {formErrors.email && (
                    <p className="text-xs text-rose-400 mt-1">{formErrors.email}</p>
                  )}
                </div>

                {/* Target Role */}
                <div className="sm:col-span-2">
                  <label className="block text-xs font-medium text-slate-300 uppercase tracking-wider font-mono mb-1.5">
                    Target Role / Position *
                  </label>
                  <div className="relative">
                    <Briefcase className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                    <input
                      type="text"
                      value={formData.targetRole}
                      onChange={(e) => handleInputChange('targetRole', e.target.value)}
                      placeholder="e.g. Senior Distributed Systems Engineer"
                      className="w-full bg-slate-900/80 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white focus:outline-none focus:border-cyan-500 transition-colors"
                    />
                  </div>
                  {formErrors.targetRole && (
                    <p className="text-xs text-rose-400 mt-1">{formErrors.targetRole}</p>
                  )}
                </div>
              </div>
            </Card>

            {/* Resume Upload Box */}
            <Card
              title="Resume & Curriculum Vitae"
              subtitle="Parses technical competencies for adaptive algorithm calibration"
              icon={<FileText className="w-5 h-5 text-indigo-400" />}
            >
              {!resumeFile ? (
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={handleDrop}
                  className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all ${
                    isDragging
                      ? 'border-cyan-400 bg-cyan-950/20'
                      : 'border-slate-700/80 hover:border-slate-600 bg-slate-900/30'
                  }`}
                >
                  <UploadCloud className="w-12 h-12 text-cyan-400 mx-auto mb-3 opacity-90" />
                  <p className="text-sm font-semibold text-white">
                    Drag and drop your resume file here
                  </p>
                  <p className="text-xs text-slate-400 mt-1 mb-4">
                    Supports PDF, DOCX, or plain TXT (Max 10MB)
                  </p>

                  <label className="inline-block">
                    <input
                      type="file"
                      accept=".pdf,.docx,.txt"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          handleFileSelect(e.target.files[0]);
                        }
                      }}
                    />
                    <span className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-200 border border-slate-700 hover:bg-slate-700 cursor-pointer transition-colors">
                      Browse Local Files
                    </span>
                  </label>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-700/80 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
                      <FileText className="w-6 h-6" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-white font-mono">
                        {resumeFile.name}
                      </div>
                      <div className="text-xs text-slate-400">
                        {formatFileSize(resumeFile.size)} • Ready for AI extraction
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setResumeFile(null)}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              )}

              {/* Parsing Progress Indicator */}
              {isSubmitting && (
                <div className="mt-4 p-4 rounded-xl bg-cyan-950/20 border border-cyan-800/40 text-center space-y-2">
                  <Spinner size="md" className="mx-auto" />
                  <p className="text-xs font-mono text-cyan-300">
                    {parsingProgress === 'creating'
                      ? 'Initializing Session (POST /sessions)...'
                      : 'Extracting skills & experience (POST /sessions/{id}/resume)...'}
                  </p>
                </div>
              )}

              {error && (
                <div className="mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center gap-2 text-xs text-rose-300">
                  <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                  <span>{error}</span>
                </div>
              )}
            </Card>

            {/* Form Submit Button */}
            <div className="flex justify-end">
              <Button
                type="submit"
                variant="cyber"
                size="lg"
                isLoading={isSubmitting}
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Parse Resume & Initialize Interview
              </Button>
            </div>
          </form>
        ) : (
          /* Parsed Confirmation Screen */
          <div className="space-y-6 animate-in fade-in zoom-in-95 duration-200">
            <Card
              title="Resume Parsed Successfully"
              subtitle={`Session ID: ${createdSessionId}`}
              icon={<CheckCircle2 className="w-5 h-5 text-emerald-400" />}
              variant="glow"
            >
              <div className="space-y-5">
                <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-900/60 border border-slate-800">
                  <div>
                    <span className="text-xs uppercase font-mono text-slate-400">
                      Calculated Experience
                    </span>
                    <div className="text-2xl font-bold font-mono text-white">
                      {parsedData.experienceYears || parsedData.experience_years || 5} Years
                    </div>
                  </div>

                  <div>
                    <span className="text-xs uppercase font-mono text-slate-400">
                      Candidate Profile
                    </span>
                    <div className="text-sm font-semibold text-cyan-400">
                      {formData.name} ({formData.targetRole})
                    </div>
                  </div>
                </div>

                {/* Extracted Skills Badges */}
                <div>
                  <h4 className="text-xs uppercase font-mono text-slate-400 mb-2 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                    Extracted Core Competencies
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {(parsedData.skills || (parsedData.claimed_skills || []).map((s) => (typeof s === 'string' ? s : s.name)) || []).map((skill, index) => (
                      <span
                        key={index}
                        className="px-3 py-1 rounded-full text-xs font-mono font-medium bg-slate-800 text-cyan-300 border border-slate-700"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-800/30 text-xs text-emerald-200 leading-relaxed">
                  ✓ The adaptive engine has loaded candidate profile parameters. Questions will
                  dynamically adjust based on answer quality and depth. Anti-cheat proctoring will
                  activate upon question render.
                </div>
              </div>
            </Card>

            <div className="flex items-center justify-between">
              <Button
                variant="ghost"
                onClick={() => {
                  setParsedData(null);
                  setResumeFile(null);
                }}
              >
                Re-upload Resume
              </Button>

              <Button
                variant="cyber"
                size="lg"
                onClick={handleStartInterview}
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Launch Adaptive Interview Room
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
