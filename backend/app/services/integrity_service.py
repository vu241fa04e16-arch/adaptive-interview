from datetime import datetime
from typing import List, Tuple
from app.models.event import SessionEvent
from app.models.session import InterviewSession
from app.schemas.report import IntegritySummary, IntegrityTimelineEntry


class IntegrityService:
    """Analyzes browser telemetry and session activity to produce explainable integrity assessments."""

    def __init__(self):
        # Configurable transparent thresholds
        self.MODERATE_TAB_SWITCH_THRESHOLD = 3
        self.ELEVATED_TAB_SWITCH_THRESHOLD = 7
        self.SUSPICIOUS_TAB_SWITCH_THRESHOLD = 10
        self.LONG_BLUR_SECONDS_THRESHOLD = 45.0
        self.LARGE_PASTE_CHARS_THRESHOLD = 400

    def analyze_events(
        self,
        events: List[SessionEvent],
        session: InterviewSession,
    ) -> IntegritySummary:
        """Processes events in chronological order, builds timeline, and evaluates explainable risk indicators."""
        # 1. Sort events chronologically
        sorted_events = sorted(events, key=lambda e: e.timestamp or e.created_at)

        timeline: List[IntegrityTimelineEntry] = []
        tab_switches = 0
        window_blurs = 0
        window_focuses = 0
        pastes_detected = 0

        risk_score = 0.0
        risk_indicators: List[str] = []
        reasons_for_flags: List[str] = []

        for e in sorted_events:
            ev_type_upper = (e.event_type or "").strip().upper()
            data = e.event_data or {}
            event_ts = e.timestamp or e.created_at

            severity = "info"
            description = f"Event recorded: {ev_type_upper}"

            if "TAB_SWITCH" in ev_type_upper:
                tab_switches += 1
                duration = data.get("duration", 0)
                if duration and duration >= 15:
                    severity = "medium"
                    description = f"Candidate switched away to another browser tab (duration: {duration}s)."
                else:
                    severity = "low"
                    description = "Candidate switched browser tabs."

            elif "BLUR" in ev_type_upper:
                window_blurs += 1
                duration = data.get("duration", 0)
                if duration and duration >= self.LONG_BLUR_SECONDS_THRESHOLD:
                    severity = "medium"
                    description = f"Interview window lost focus for {duration} seconds."
                else:
                    severity = "low"
                    description = "Interview window lost focus."

            elif "FOCUS" in ev_type_upper:
                window_focuses += 1
                severity = "info"
                description = "Interview window regained active focus."

            elif "PASTE" in ev_type_upper:
                pastes_detected += 1
                chars = data.get("characters") or data.get("length") or 0
                if chars >= self.LARGE_PASTE_CHARS_THRESHOLD:
                    severity = "medium"
                    description = f"External clipboard content pasted into answer input ({chars} characters)."
                else:
                    severity = "low"
                    description = "Clipboard paste action detected."

            elif "START" in ev_type_upper:
                severity = "info"
                description = "Candidate started the interview session."

            elif "COMPLETE" in ev_type_upper:
                severity = "info"
                description = "Interview session finalized by candidate."

            timeline.append(
                IntegrityTimelineEntry(
                    timestamp=event_ts,
                    event_type=e.event_type,
                    severity=severity,
                    description=description,
                )
            )

        # 2. Transparent Rule-Based Risk Evaluation
        # A. Tab switches evaluation
        if tab_switches >= self.SUSPICIOUS_TAB_SWITCH_THRESHOLD:
            risk_score += 6.0
            msg = f"Elevated tab switches ({tab_switches} occurrences) observed during active assessment."
            risk_indicators.append(msg)
            reasons_for_flags.append(msg)
        elif tab_switches >= self.ELEVATED_TAB_SWITCH_THRESHOLD:
            risk_score += 3.5
            risk_indicators.append(
                f"Moderate frequency of tab switches ({tab_switches} occurrences). Recommend debrief inquiry."
            )
        elif tab_switches >= self.MODERATE_TAB_SWITCH_THRESHOLD:
            risk_score += 1.5
            risk_indicators.append(
                f"Occasional tab switches ({tab_switches} occurrences) detected; likely normal workspace multitasking or system notifications."
            )

        # B. Window blur duration check
        long_blurs = [
            e for e in sorted_events
            if "BLUR" in (e.event_type or "").upper() and (e.event_data or {}).get("duration", 0) >= self.LONG_BLUR_SECONDS_THRESHOLD
        ]
        if long_blurs:
            risk_score += 2.0
            msg = f"Extended window unfocus periods detected ({len(long_blurs)} event(s) exceeding {self.LONG_BLUR_SECONDS_THRESHOLD}s)."
            risk_indicators.append(msg)
            reasons_for_flags.append(msg)

        # C. Large clipboard paste check
        large_pastes = [
            e for e in sorted_events
            if "PASTE" in (e.event_type or "").upper() and ((e.event_data or {}).get("characters") or (e.event_data or {}).get("length") or 0) >= self.LARGE_PASTE_CHARS_THRESHOLD
        ]
        if large_pastes:
            risk_score += 2.0
            msg = f"Large clipboard paste detected ({len(large_pastes)} occurrence(s) with >= {self.LARGE_PASTE_CHARS_THRESHOLD} characters)."
            risk_indicators.append(msg)

        # Cap risk score
        risk_score = round(min(10.0, max(0.0, risk_score)), 1)

        # Classify risk level
        if risk_score >= 6.0 or tab_switches >= self.SUSPICIOUS_TAB_SWITCH_THRESHOLD:
            risk_level = "high"
            suspicious = True
        elif risk_score >= 3.0:
            risk_level = "medium"
            suspicious = False
        else:
            risk_level = "low"
            suspicious = False

        if not risk_indicators:
            risk_indicators.append("Standard candidate telemetry recorded with no unusual focus disruptions.")

        return IntegritySummary(
            total_events=len(sorted_events),
            tab_switches=tab_switches,
            window_blurs=window_blurs,
            window_focuses=window_focuses,
            pastes_detected=pastes_detected,
            suspicious_activity_flag=suspicious,
            risk_level=risk_level,
            risk_score=risk_score,
            risk_indicators=risk_indicators,
            reasons_for_flags=reasons_for_flags,
            timeline=timeline,
        )
