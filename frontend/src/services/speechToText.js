/**
 * Speech Recognition and Audio Capture Service
 * Provides Web Speech API integration, MediaRecorder audio streaming,
 * and robust fallbacks for browsers without SpeechRecognition.
 */

// Check browser recognition support
export function isSpeechRecognitionSupported() {
  return typeof window !== 'undefined' && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window);
}

/**
 * Creates and configures a SpeechRecognition instance
 */
export function createSpeechRecognizer({ onResult, onError, onEnd }) {
  if (!isSpeechRecognitionSupported()) {
    return null;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();

  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = 'en-US';
  recognition.maxAlternatives = 1;

  recognition.onresult = (event) => {
    let finalTranscript = '';
    let interimTranscript = '';

    for (let i = event.resultIndex; i < event.results.length; ++i) {
      const transcriptSegment = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += transcriptSegment + ' ';
      } else {
        interimTranscript += transcriptSegment;
      }
    }

    if (onResult) {
      onResult({
        final: finalTranscript.trim(),
        interim: interimTranscript.trim(),
      });
    }
  };

  recognition.onerror = (event) => {
    console.warn('SpeechRecognition error:', event.error);
    if (onError) onError(event.error);
  };

  recognition.onend = () => {
    if (onEnd) onEnd();
  };

  return recognition;
}

/**
 * Audio Stream and MediaRecorder Manager
 * Handles microphone capture, MediaStream, and raw audio Blob production.
 */
export class AudioStreamCapture {
  constructor() {
    this.stream = null;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.audioContext = null;
    this.analyser = null;
  }

  /**
   * Request microphone stream and setup audio analyzer
   */
  async requestMicStream() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('getUserMedia is not supported on this browser.');
    }

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    return this.stream;
  }

  /**
   * Setup Web Audio API Analyser for live waveforms
   */
  getAudioFrequencyData() {
    if (!this.stream) return null;

    if (!this.audioContext) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      this.audioContext = new AudioContextClass();
      const source = this.audioContext.createMediaStreamSource(this.stream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 64;
      source.connect(this.analyser);
    }

    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteFrequencyData(dataArray);
    return dataArray;
  }

  /**
   * Start recording audio blob
   */
  startRecording() {
    if (!this.stream) {
      throw new Error('Microphone stream not initialized');
    }

    this.audioChunks = [];
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';

    this.mediaRecorder = new MediaRecorder(this.stream, { mimeType });

    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        this.audioChunks.push(e.data);
      }
    };

    this.mediaRecorder.start(250); // Slice chunks every 250ms
  }

  /**
   * Stop recording and return audio Blob
   */
  async stopRecording() {
    return new Promise((resolve) => {
      if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
        resolve(null);
        return;
      }

      this.mediaRecorder.onstop = () => {
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
        resolve(audioBlob);
      };

      this.mediaRecorder.stop();
    });
  }

  /**
   * Clean up hardware tracks and audio contexts
   */
  cleanup() {
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
    if (this.audioContext && this.audioContext.state !== 'closed') {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }
  }
}
