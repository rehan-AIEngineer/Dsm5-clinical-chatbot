// components/ContextPanel.jsx
// Collapsible side panel: "Clinical context" tab + "Grief workbook" (calendar) tab
// No raw JSON, no technical labels, no "pgvector" mention

import React, { useState, useEffect } from "react";
import {
  saveGriefEntry,
  getGriefEntry,
  getGriefCalendarDates,
  deleteGriefEntry,
} from "../api/chatbotApi";

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const MONTHS = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];

function buildCalendarDays(year, month) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  return cells;
}

function toDateStr(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export default function ContextPanel({
  isOpen,
  onClose,
  sessionId,
  // Clinical context props (lifted to App.jsx)
  featureMode, setFeatureMode,
  userRole, setUserRole,
  diagnosisStatus, setDiagnosisStatus,
  reportedSymptoms, setReportedSymptoms,
  durationMonths, setDurationMonths,
  substanceUse, setSubstanceUse,
  relationship, setRelationship,
  // Grief props
  lossRelationship, setLossRelationship,
  timeSinceLoss, setTimeSinceLoss,
  griefThemes, setGriefThemes,
  // Calendar reflection passed up
  calendarText, setCalendarText,
  selectedDate, setSelectedDate,
  onOpenReflectionChat,
  onSelectChat,
}) {
  const [tab, setTab] = useState("clinical"); // "clinical" | "grief"

  // Calendar state
  const today = new Date();
  const [calYear, setCalYear] = useState(today.getFullYear());
  const [calMonth, setCalMonth] = useState(today.getMonth());
  const [markedDates, setMarkedDates] = useState([]); // ["YYYY-MM-DD", ...]
  const [savingReflection, setSavingReflection] = useState(false);
  const [saveConfirm, setSaveConfirm] = useState(false);
  const [currentEntry, setCurrentEntry] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Load marked dates when session changes
  useEffect(() => {
    if (sessionId && !sessionId.startsWith("temp-")) {
      getGriefCalendarDates(sessionId)
        .then((res) => res?.dates && setMarkedDates(res.dates))
        .catch(() => {});
    }
  }, [sessionId]);

  // Load reflection text when selectedDate changes
  useEffect(() => {
    setShowDeleteConfirm(false);
    if (!selectedDate || !sessionId || sessionId.startsWith("temp-")) {
      setCalendarText("");
      setCurrentEntry(null);
      return;
    }
    getGriefEntry(selectedDate, sessionId)
      .then((res) => {
        if (res?.entry) {
          setCalendarText(res.entry.entry_text || "");
          setCurrentEntry(res.entry);
        } else {
          setCalendarText("");
          setCurrentEntry(null);
        }
      })
      .catch(() => {
        setCalendarText("");
        setCurrentEntry(null);
      });
  }, [selectedDate, sessionId]);

  const handleSaveReflection = async () => {
    if (!calendarText.trim() || !sessionId || sessionId.startsWith("temp-")) return;
    setSavingReflection(true);
    setSaveConfirm(false);
    try {
      const res = await saveGriefEntry(selectedDate, calendarText, sessionId, { mode: "grief_workbook" });
      setSaveConfirm(true);
      if (res?.id) {
        setCurrentEntry((prev) => ({
          ...prev,
          id: res.id,
          entry_date: selectedDate,
          entry_text: calendarText,
        }));
      }
      if (!markedDates.includes(selectedDate)) {
        setMarkedDates((prev) => [...prev, selectedDate]);
      }
      setTimeout(() => setSaveConfirm(false), 3000);
    } catch {
      // silent fail — user can retry
    } finally {
      setSavingReflection(false);
    }
  };

  const handleDeleteReflection = async () => {
    if (!selectedDate || deleting) return;
    setDeleting(true);
    try {
      await deleteGriefEntry(selectedDate, currentEntry?.id, sessionId);
      setMarkedDates((prev) => prev.filter((d) => d !== selectedDate));
      setCalendarText("");
      setCurrentEntry(null);
      setShowDeleteConfirm(false);
    } catch (err) {
      console.error("Failed to delete reflection:", err);
    } finally {
      setDeleting(false);
    }
  };

  const handleOpenConversationClick = () => {
    if (!calendarText.trim()) return;
    if (onOpenReflectionChat) {
      onOpenReflectionChat(
        selectedDate,
        calendarText,
        currentEntry?.session_id || null,
        currentEntry?.id || null
      );
    }
  };

  const prevMonth = () => {
    if (calMonth === 0) { setCalYear((y) => y - 1); setCalMonth(11); }
    else setCalMonth((m) => m - 1);
  };
  const nextMonth = () => {
    if (calMonth === 11) { setCalYear((y) => y + 1); setCalMonth(0); }
    else setCalMonth((m) => m + 1);
  };

  const calDays = buildCalendarDays(calYear, calMonth);
  const todayStr = toDateStr(today.getFullYear(), today.getMonth(), today.getDate());

  const hasSavedEntry = markedDates.includes(selectedDate) || !!currentEntry;

  if (!isOpen) return null;

  return (
    <div className="context-panel" style={{ position: "relative" }}>
      {/* Header */}
      <div className="context-panel-header">
        <p className="context-panel-title">Your context</p>
        <button className="context-panel-close" onClick={onClose} title="Close">✕</button>

        {/* Tab switcher */}
        <div className="context-tabs">
          <button
            className={`context-tab${tab === "clinical" ? " active" : ""}`}
            onClick={() => setTab("clinical")}
          >
            Clinical context
          </button>
          <button
            className={`context-tab${tab === "grief" ? " active" : ""}`}
            onClick={() => setTab("grief")}
          >
            Grief workbook
          </button>
        </div>
      </div>

      {/* Body with auto scroll */}
      <div className="context-panel-body">
        {/* ── Clinical context tab ── */}
        {tab === "clinical" && (
          <>
            <p className="context-optional-note">
              All fields are optional. Sharing what you're comfortable with helps us provide more relevant support.
            </p>

            <div className="field">
              <label>I am the</label>
              <select value={userRole} onChange={(e) => setUserRole(e.target.value)}>
                <option value="caregiver">A caregiver or family member</option>
                <option value="individual">The person experiencing symptoms</option>
              </select>
            </div>

            <div className="field">
              <label>My relationship to them</label>
              <input
                type="text"
                value={relationship}
                onChange={(e) => setRelationship(e.target.value)}
                placeholder="e.g. spouse, sibling, parent…"
              />
            </div>

            <div className="field">
              <label>Current situation</label>
              <select value={diagnosisStatus} onChange={(e) => setDiagnosisStatus(e.target.value)}>
                <option value="unknown">Not yet diagnosed</option>
                <option value="suspected">Symptoms present, seeking help</option>
                <option value="formal_diagnosis">Diagnosis already confirmed</option>
              </select>
            </div>

            <div className="field">
              <label>Symptoms noticed (optional)</label>
              <input
                type="text"
                value={reportedSymptoms}
                onChange={(e) => setReportedSymptoms(e.target.value)}
                placeholder="Describe what you've observed, in your own words…"
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div className="field">
                <label>How long (approx.)</label>
                <select value={durationMonths} onChange={(e) => setDurationMonths(Number(e.target.value))}>
                  <option value={1}>About 1 month</option>
                  <option value={3}>About 3 months</option>
                  <option value={6}>About 6 months</option>
                  <option value={12}>1 year or more</option>
                </select>
              </div>
              <div className="field">
                <label>Substance use</label>
                <select value={substanceUse ? "yes" : "no"} onChange={(e) => setSubstanceUse(e.target.value === "yes")}>
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                </select>
              </div>
            </div>
          </>
        )}

        {/* ── Grief workbook tab ── */}
        {tab === "grief" && (
          <>
            <p className="grief-heading">Your grief calendar</p>
            <p className="grief-subtext">
              A quiet place to mark your days and keep small reflections. Empty days don't mean anything is wrong.
            </p>

            {/* Grief context fields */}
            <div className="field">
              <label>Who you lost</label>
              <input
                type="text"
                value={lossRelationship}
                onChange={(e) => setLossRelationship(e.target.value)}
                placeholder="e.g. my husband, my mother…"
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div className="field">
                <label>Time since loss</label>
                <select value={timeSinceLoss} onChange={(e) => setTimeSinceLoss(e.target.value)}>
                  <option value="2_months">About 2 months</option>
                  <option value="6_months">About 6 months</option>
                  <option value="12_months">About a year</option>
                  <option value="18_months">More than a year</option>
                </select>
              </div>
              <div className="field">
                <label>Themes (optional)</label>
                <input
                  type="text"
                  value={griefThemes}
                  onChange={(e) => setGriefThemes(e.target.value)}
                  placeholder="e.g. guilt…"
                />
              </div>
            </div>

            {/* Calendar grid */}
            <div className="cal-nav">
              <button className="cal-nav-btn" onClick={prevMonth}>‹</button>
              <span className="cal-month-label">{MONTHS[calMonth]} {calYear}</span>
              <button className="cal-nav-btn" onClick={nextMonth}>›</button>
            </div>

            <div className="cal-grid">
              {WEEKDAYS.map((d) => (
                <div key={d} className="cal-weekday">{d}</div>
              ))}
              {calDays.map((day, idx) => {
                if (!day) return <div key={`e-${idx}`} />;
                const dateStr = toDateStr(calYear, calMonth, day);
                const isSelected = dateStr === selectedDate;
                const isToday = dateStr === todayStr;
                const hasEntry = markedDates.includes(dateStr);
                return (
                  <button
                    key={dateStr}
                    className={`cal-day${isSelected ? " selected" : ""}${isToday ? " today" : ""}`}
                    onClick={() => setSelectedDate(dateStr)}
                  >
                    {day}
                    {hasEntry && <span className="cal-dot" />}
                  </button>
                );
              })}
            </div>

            {/* Reflection for selected date */}
            <div className="cal-reflection">
              <p className="cal-reflection-date">
                {selectedDate
                  ? new Date(selectedDate + "T00:00:00").toLocaleDateString("en-US", {
                      weekday: "long", month: "long", day: "numeric",
                    })
                  : "Select a date above"}
              </p>
              <textarea
                placeholder="Write a few words about this day, if you'd like…"
                value={calendarText}
                onChange={(e) => setCalendarText(e.target.value)}
              />
              <button
                className="btn-save-reflection"
                onClick={handleSaveReflection}
                disabled={savingReflection || !calendarText.trim()}
              >
                {savingReflection ? "Saving…" : "Save reflection"}
              </button>
              {saveConfirm && (
                <p className="save-confirm">
                  <span>✓</span> Saved
                </p>
              )}

              {/* Action buttons when a saved reflection exists */}
              {(hasSavedEntry || calendarText.trim()) && (
                <>
                  {showDeleteConfirm ? (
                    <div className="delete-confirm-box">
                      <p className="delete-confirm-text">
                        Are you sure you want to delete this reflection?
                      </p>
                      <div className="delete-confirm-actions">
                        <button
                          className="btn-confirm-cancel"
                          onClick={() => setShowDeleteConfirm(false)}
                          disabled={deleting}
                        >
                          Cancel
                        </button>
                        <button
                          className="btn-confirm-delete"
                          onClick={handleDeleteReflection}
                          disabled={deleting}
                        >
                          {deleting ? "Deleting…" : "Delete"}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="reflection-actions">
                      <button
                        className="btn-open-conversation"
                        onClick={handleOpenConversationClick}
                        disabled={!calendarText.trim()}
                        title={
                          currentEntry?.session_id
                            ? "Continue conversation in existing chat"
                            : "Start new conversation with this reflection"
                        }
                      >
                        <span>💬</span> Open Conversation
                      </button>
                      {hasSavedEntry && (
                        <button
                          className="btn-delete-reflection"
                          onClick={() => setShowDeleteConfirm(true)}
                          title="Delete reflection and remove from memory"
                        >
                          <span>🗑️</span> Delete
                        </button>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
