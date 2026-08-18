// TestingDashboard.jsx — Prop-driven: Session from App.jsx, Pipeline + Zone A/B/C
import React, { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  saveGriefEntry,
  getGriefEntry,
  getGriefCalendarDates,
} from '../api/chatbotApi'

// ============================================================
// Props from App.jsx:
//   sessionId   — active chat session ID (from sidebar)
//   messages    — array of {role, content, timestamp?, debug?}
//   loading     — pipeline running state
//   onSend      — async (text, sessionContext) => debugInfo
//   onNewSession— creates a new session via sidebar
//   error       — error string from App.jsx
//   chatTitle   — current chat title for header
// ============================================================

export default function TestingDashboard({
  sessionId,
  messages = [],
  loading = false,
  onSend,
  onNewSession,
  error,
  chatTitle,
}) {
  // ---- Zone A: Context Injector State (internal) ----
  const [featureMode, setFeatureMode] = useState('clinical_support')
  const [userRole, setUserRole] = useState('caregiver')
  const [diagnosisStatus, setDiagnosisStatus] = useState('unknown')
  const [reportedSymptoms, setReportedSymptoms] = useState('hearing voices, paranoid')
  const [durationMonths, setDurationMonths] = useState('3')
  const [substanceUse, setSubstanceUse] = useState('none reported')
  const [relationship, setRelationship] = useState('Brother')

  // Grief Mode Inputs
  const [lossRelationship, setLossRelationship] = useState('Spouse')
  const [timeSinceLoss, setTimeSinceLoss] = useState('6_months')
  const [griefThemes, setGriefThemes] = useState('guilt, identity disruption')

  // Grief Calendar State (internal)
  const [selectedDate, setSelectedDate] = useState(
    () => new Date().toISOString().split('T')[0]
  )
  const [calendarText, setCalendarText] = useState('')
  const [markedDates, setMarkedDates] = useState([])
  const [savingCalendar, setSavingCalendar] = useState(false)
  const [calendarNotice, setCalendarNotice] = useState('')

  // ---- Zone B: Chat input state ----
  const [inputMessage, setInputMessage] = useState('')
  const messagesEndRef = useRef(null)

  // ---- Zone C: Pipeline Debugger ----
  const [debugData, setDebugData] = useState(null)

  // Auto-scroll Zone B on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Derive latest debug from last assistant message (handles session reload)
  useEffect(() => {
    const lastDebug = [...messages]
      .reverse()
      .find((m) => m.role === 'assistant' && m.debug)
    if (lastDebug?.debug) {
      setDebugData(lastDebug.debug)
    }
  }, [messages])

  // Reload calendar dates when session changes
  useEffect(() => {
    if (sessionId && !sessionId.startsWith('temp-')) {
      fetchCalendarDates()
    }
  }, [sessionId])

  // Reload calendar entry when date changes
  useEffect(() => {
    if (selectedDate && sessionId && !sessionId.startsWith('temp-')) {
      loadCalendarEntry(selectedDate)
    }
  }, [selectedDate, sessionId])

  const fetchCalendarDates = async () => {
    try {
      const res = await getGriefCalendarDates(sessionId)
      if (res?.dates) setMarkedDates(res.dates)
    } catch {
      // Calendar dates are non-critical, silently fail
    }
  }

  const loadCalendarEntry = async (dateStr) => {
    try {
      const res = await getGriefEntry(dateStr, sessionId)
      setCalendarText(res?.entry?.entry_text || '')
    } catch {
      setCalendarText('')
    }
  }

  const handleSaveCalendarEntry = async () => {
    if (!calendarText.trim()) return
    if (!sessionId || sessionId.startsWith('temp-')) {
      setCalendarNotice('Send a message first to start a session.')
      return
    }
    setSavingCalendar(true)
    setCalendarNotice('')
    try {
      await saveGriefEntry(selectedDate, calendarText, sessionId, {
        mode: featureMode,
      })
      setCalendarNotice('Saved to Postgres & pgvector!')
      fetchCalendarDates()
      setTimeout(() => setCalendarNotice(''), 3000)
    } catch {
      setCalendarNotice('Failed to save entry.')
    } finally {
      setSavingCalendar(false)
    }
  }

  // Build structured session_context from Zone A
  const buildSessionContext = () => {
    if (featureMode === 'grief_workbook') {
      return {
        feature_mode: 'grief_workbook',
        user_role: 'grieving',
        grief_data: {
          user_memory_profile: {
            deceased_or_loss: lossRelationship,
            time_since_loss: timeSinceLoss,
            grief_themes: griefThemes
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean),
          },
          current_workbook_entry:
            calendarText
              ? { entry_date: selectedDate, entry_text: calendarText }
              : null,
        },
      }
    }
    return {
      feature_mode: 'clinical_support',
      user_role: userRole,
      diagnosis_status: diagnosisStatus,
      clinical_data: {
        relationship,
        reported_symptoms: reportedSymptoms
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        duration_months: durationMonths,
        substance_use: substanceUse,
      },
    }
  }

  // Send message through App.jsx → 4-agent pipeline → DB session save
  const handleSendMessage = async (e) => {
    e?.preventDefault()
    if (!inputMessage.trim() || loading) return

    const text = inputMessage.trim()
    setInputMessage('')

    const context = buildSessionContext()
    const debugInfo = await onSend(text, context)
    if (debugInfo) setDebugData(debugInfo)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 font-sans overflow-hidden">

      {/* ── Header ── */}
      <header className="h-12 px-5 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between shrink-0 backdrop-blur">
        <div className="flex items-center gap-3">
          <span className="text-lg">🤖</span>
          <h1 className="font-bold text-sm text-emerald-400 tracking-wide truncate max-w-xs">
            {chatTitle || 'DSM-5-TR Clinical Assistant'}
          </h1>
          <span className="hidden sm:inline px-2 py-0.5 text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full">
            4-Agent + Memory
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          {sessionId && !sessionId.startsWith('temp-') && (
            <span className="hidden md:flex items-center gap-1.5 bg-slate-800/80 px-3 py-1 rounded border border-slate-700 font-mono text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              {sessionId.substring(0, 14)}…
            </span>
          )}
          <button
            onClick={onNewSession}
            className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white font-medium rounded transition shadow-sm text-xs"
          >
            + New Chat
          </button>
        </div>
      </header>

      {/* ── 3-Zone Main Grid ── */}
      <div className="flex-1 grid grid-cols-12 gap-0 overflow-hidden divide-x divide-slate-800 min-h-0">

        {/* ================================================================ */}
        {/* ZONE A: Context Injector & Grief Calendar (3 cols)               */}
        {/* ================================================================ */}
        <div className="col-span-3 bg-slate-900/40 p-4 flex flex-col gap-4 overflow-y-auto custom-scrollbar">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2 shrink-0">
            <h2 className="font-bold text-xs text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <span>🎛️</span> Zone A: Context Injector
            </h2>
            <span className="text-[9px] text-slate-500 bg-slate-800 px-2 py-0.5 rounded">
              Session Persistent
            </span>
          </div>

          {/* Mode Switcher */}
          <div className="flex bg-slate-900 p-1 rounded-lg border border-slate-800 shrink-0">
            <button
              onClick={() => setFeatureMode('clinical_support')}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition ${
                featureMode === 'clinical_support'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🏥 Clinical
            </button>
            <button
              onClick={() => setFeatureMode('grief_workbook')}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition ${
                featureMode === 'grief_workbook'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🕯️ Grief
            </button>
          </div>

          {/* Clinical Support Form */}
          {featureMode === 'clinical_support' && (
            <div className="space-y-3 text-xs">
              <ZoneAField label="User Role">
                <select
                  value={userRole}
                  onChange={(e) => setUserRole(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  <option value="caregiver">Caregiver (family/loved one)</option>
                  <option value="individual">Individual (self)</option>
                </select>
              </ZoneAField>

              <ZoneAField label="Diagnosis Status">
                <select
                  value={diagnosisStatus}
                  onChange={(e) => setDiagnosisStatus(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  <option value="unknown">Unknown / Not Diagnosed</option>
                  <option value="suspected">Suspected</option>
                  <option value="known">Known / Confirmed</option>
                </select>
              </ZoneAField>

              <ZoneAField label="Relationship">
                <input
                  type="text"
                  value={relationship}
                  onChange={(e) => setRelationship(e.target.value)}
                  placeholder="e.g. Brother, Parent"
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </ZoneAField>

              <ZoneAField label="Reported Symptoms">
                <textarea
                  rows={2}
                  value={reportedSymptoms}
                  onChange={(e) => setReportedSymptoms(e.target.value)}
                  placeholder="Comma separated symptoms"
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500 resize-none"
                />
              </ZoneAField>

              <div className="grid grid-cols-2 gap-2">
                <ZoneAField label="Duration (Mo)">
                  <input
                    type="text"
                    value={durationMonths}
                    onChange={(e) => setDurationMonths(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </ZoneAField>
                <ZoneAField label="Substance Use">
                  <input
                    type="text"
                    value={substanceUse}
                    onChange={(e) => setSubstanceUse(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </ZoneAField>
              </div>
            </div>
          )}

          {/* Grief Workbook Form */}
          {featureMode === 'grief_workbook' && (
            <div className="space-y-3 text-xs">
              <ZoneAField label="Loss Relationship">
                <input
                  type="text"
                  value={lossRelationship}
                  onChange={(e) => setLossRelationship(e.target.value)}
                  placeholder="e.g. Spouse, Brother"
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-purple-500"
                />
              </ZoneAField>

              <ZoneAField label="Time Since Loss">
                <select
                  value={timeSinceLoss}
                  onChange={(e) => setTimeSinceLoss(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-purple-500"
                >
                  <option value="2_months">2 Months</option>
                  <option value="6_months">6 Months</option>
                  <option value="12_months">12 Months</option>
                  <option value="18_months">18+ Months (PGD threshold)</option>
                </select>
              </ZoneAField>

              <ZoneAField label="Grief Themes">
                <input
                  type="text"
                  value={griefThemes}
                  onChange={(e) => setGriefThemes(e.target.value)}
                  placeholder="e.g. guilt, identity disruption"
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-purple-500"
                />
              </ZoneAField>
            </div>
          )}

          {/* Grief Calendar */}
          <div className="pt-3 border-t border-slate-800 space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-purple-300 flex items-center gap-1.5 text-xs">
                📅 Grief Calendar Memory
              </span>
              {markedDates.length > 0 && (
                <span className="text-[9px] bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded-full">
                  {markedDates.length} entries
                </span>
              )}
            </div>

            <ZoneAField label="Date">
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-purple-500"
              />
            </ZoneAField>

            <ZoneAField label="Reflection">
              <textarea
                rows={3}
                value={calendarText}
                onChange={(e) => setCalendarText(e.target.value)}
                placeholder="Write your workbook reflection for this date..."
                className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-purple-500 resize-none"
              />
            </ZoneAField>

            <button
              onClick={handleSaveCalendarEntry}
              disabled={savingCalendar || !calendarText.trim()}
              className="w-full py-1.5 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 text-white font-medium rounded transition text-xs"
            >
              {savingCalendar ? 'Saving…' : '💾 Save to pgvector Memory'}
            </button>

            {calendarNotice && (
              <p className="text-[11px] text-emerald-400 text-center font-medium animate-pulse">
                {calendarNotice}
              </p>
            )}
          </div>

          {/* Active Session JSON Preview */}
          <div className="mt-auto pt-3 border-t border-slate-800">
            <details className="text-[11px] text-slate-400">
              <summary className="cursor-pointer font-medium hover:text-slate-300">
                View Active Context JSON
              </summary>
              <pre className="mt-2 p-2 bg-slate-950 rounded border border-slate-800 font-mono text-[10px] overflow-x-auto text-emerald-400 max-h-28">
                {JSON.stringify(buildSessionContext(), null, 2)}
              </pre>
            </details>
          </div>
        </div>

        {/* ================================================================ */}
        {/* ZONE B: Chat Interface — pipeline + session save (5 cols)        */}
        {/* ================================================================ */}
        <div className="col-span-5 bg-slate-950 flex flex-col h-full overflow-hidden min-h-0">
          {/* Zone B Header */}
          <div className="h-9 px-4 bg-slate-900/60 border-b border-slate-800 flex items-center justify-between shrink-0">
            <h2 className="font-bold text-xs text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <span>💬</span> Zone B: Chat
            </h2>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                4-Agent Engine
              </span>
              <span className="text-[10px] text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                Session Saved ✓
              </span>
            </div>
          </div>

          {/* Messages area */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4 custom-scrollbar min-h-0">
            {messages.filter((m) => m.role !== 'system').length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 space-y-3">
                <div className="w-14 h-14 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-2xl shadow-inner">
                  💬
                </div>
                <div>
                  <p className="font-semibold text-slate-300 text-sm">
                    Start a Conversation
                  </p>
                  <p className="text-xs text-slate-500 mt-1 max-w-xs leading-relaxed">
                    Configure Zone A on the left, then type below. All messages
                    are saved to your session history.
                  </p>
                </div>
                <div className="text-[11px] text-slate-600 bg-slate-900/60 px-4 py-2 rounded-lg border border-slate-800 max-w-xs">
                  🇵🇰 Crisis? Call Umang: <span className="text-emerald-400 font-mono">0311-7786264</span>
                </div>
              </div>
            ) : (
              messages
                .filter((m) => m.role !== 'system')
                .map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex flex-col ${
                      msg.role === 'user' ? 'items-end' : 'items-start'
                    }`}
                  >
                    <div
                      className={`max-w-[92%] rounded-xl p-3.5 text-xs leading-relaxed shadow-sm ${
                        msg.role === 'user'
                          ? 'bg-emerald-700 text-white rounded-br-none'
                          : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none'
                      }`}
                    >
                      {msg.role === 'user' ? (
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      ) : msg.content === '' ? (
                        <div className="flex items-center gap-1.5 text-slate-400">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                      ) : (
                        <div className="prose prose-invert prose-xs max-w-none">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      )}
                    </div>
                    {msg.timestamp && (
                      <span className="text-[10px] text-slate-600 mt-1 px-1 font-mono">
                        {msg.timestamp}
                      </span>
                    )}
                  </div>
                ))
            )}

            {loading && messages[messages.length - 1]?.content !== '' && (
              <div className="flex items-center gap-2 text-slate-400 text-xs p-3 bg-slate-900/50 rounded-lg border border-slate-800 animate-pulse w-max">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                <span>Running 4-Agent Pipeline…</span>
              </div>
            )}

            {error && (
              <div className="p-3 bg-rose-950/40 border border-rose-800 text-rose-300 rounded-lg text-xs">
                ⚠️ {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Chat Input */}
          <form
            onSubmit={handleSendMessage}
            className="p-3 bg-slate-900/80 border-t border-slate-800 shrink-0"
          >
            <div className="flex gap-2">
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about symptoms, clinical guidance, or loss…"
                disabled={loading}
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={loading || !inputMessage.trim()}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs rounded-lg transition shadow-sm"
              >
                {loading ? '…' : 'Send'}
              </button>
            </div>
            <p className="text-[10px] text-slate-600 mt-1.5 text-center">
              Not a substitute for professional medical advice. Crisis: Umang 0311-7786264 · Rescue 1122
            </p>
          </form>
        </div>

        {/* ================================================================ */}
        {/* ZONE C: Live 4-Agent Pipeline Debugger (4 cols)                 */}
        {/* ================================================================ */}
        <div className="col-span-4 bg-slate-900/40 p-4 flex flex-col gap-3 overflow-y-auto custom-scrollbar">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2 shrink-0">
            <h2 className="font-bold text-xs text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <span>🐞</span> Zone C: Pipeline Debugger
            </h2>
            {debugData?.metrics?.total_time_ms && (
              <span className="text-[10px] font-mono bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-500/30">
                ⚡ {debugData.metrics.total_time_ms} ms
              </span>
            )}
          </div>

          {!debugData ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-500">
              <span className="text-3xl mb-2">📊</span>
              <p className="text-xs leading-relaxed">
                Send a message in Zone B to see live 4-agent telemetry.
              </p>
            </div>
          ) : (
            <div className="space-y-3 text-xs">

              {/* Agent 1 */}
              <DebugBox
                title="🔍 Agent 1: Guardrail"
                color="emerald"
                timeMs={debugData.metrics?.agent1_time_ms}
              >
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <span className="px-2 py-0.5 text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 rounded border border-emerald-500/30">
                    {debugData.agent1?.category || 'N/A'}
                  </span>
                  {debugData.agent1?.passive_risk_flag && (
                    <span className="px-2 py-0.5 text-[10px] font-semibold bg-amber-500/20 text-amber-300 rounded border border-amber-500/30">
                      ⚠️ Passive Risk
                    </span>
                  )}
                </div>
                {debugData.agent1?.reasoning && (
                  <p className="text-[11px] text-slate-400 pt-1 leading-snug">
                    {debugData.agent1.reasoning}
                  </p>
                )}
              </DebugBox>

              {/* Agent 2 */}
              <DebugBox
                title="🧠 Agent 2: Clinical Engine"
                color="cyan"
                timeMs={debugData.metrics?.agent2_time_ms}
              >
                <div className="bg-slate-900 p-2 rounded border border-slate-800 overflow-x-auto max-h-36 mt-1">
                  <pre className="text-[10px] font-mono text-cyan-300 leading-tight">
                    {JSON.stringify(debugData.agent2, null, 2)}
                  </pre>
                </div>
              </DebugBox>

              {/* Agent 3 */}
              <DebugBox
                title="❤️ Agent 3: Empathy Synthesizer"
                color="purple"
                timeMs={debugData.metrics?.agent3_time_ms}
              >
                <div className="p-2 bg-slate-900 rounded border border-slate-800 text-[11px] text-slate-300 max-h-28 overflow-y-auto leading-relaxed mt-1">
                  {debugData.agent3_draft || '(No draft)'}
                </div>
              </DebugBox>

              {/* Agent 4 */}
              <DebugBox
                title="✅ Agent 4: Safety Auditor"
                color="emerald"
                timeMs={debugData.metrics?.agent4_time_ms}
              >
                <div className="p-2 bg-slate-900 rounded border border-slate-800 text-[11px] text-emerald-300 max-h-28 overflow-y-auto leading-relaxed mt-1">
                  {debugData.agent4_final || '(No final response)'}
                </div>
              </DebugBox>

              {/* Latency Breakdown */}
              {debugData.metrics && (
                <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 space-y-1.5">
                  <p className="text-[11px] font-bold text-slate-300 mb-2">⏱ Latency Breakdown</p>
                  {[
                    ['Agent 1', debugData.metrics.agent1_time_ms],
                    ['Agent 2', debugData.metrics.agent2_time_ms],
                    ['Agent 3', debugData.metrics.agent3_time_ms],
                    ['Agent 4', debugData.metrics.agent4_time_ms],
                    ['Total', debugData.metrics.total_time_ms],
                  ].map(([label, ms]) => (
                    <div key={label} className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-400">{label}</span>
                      <span className="font-mono text-emerald-400">
                        {ms != null ? `${ms} ms` : '—'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Helper sub-components ──────────────────────────────────────────────────

function ZoneAField({ label, children }) {
  return (
    <div>
      <label className="block text-slate-400 mb-1 font-medium text-[11px]">{label}</label>
      {children}
    </div>
  )
}

const colorMap = {
  emerald: 'text-emerald-400',
  cyan: 'text-cyan-400',
  purple: 'text-purple-400',
}

function DebugBox({ title, color = 'emerald', timeMs, children }) {
  return (
    <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 space-y-1 shadow-sm">
      <div className="flex items-center justify-between">
        <span className={`font-bold text-[11px] flex items-center gap-1 ${colorMap[color] || colorMap.emerald}`}>
          {title}
        </span>
        {timeMs != null && (
          <span className="text-[10px] text-slate-500 font-mono">{timeMs} ms</span>
        )}
      </div>
      {children}
    </div>
  )
}
