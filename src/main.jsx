import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Camera,
  Check,
  Gauge,
  Loader2,
  Mic,
  MonitorStop,
  Pause,
  Play,
  RotateCcw,
  Settings,
  SlidersHorizontal,
  Square,
  Trash2,
  Volume2
} from "lucide-react";
import "./styles.css";

const isDesktopApiReady = () => typeof window.pywebview?.api?.get_state === "function";

const waitForDesktopApi = () => {
  if (isDesktopApiReady()) {
    return Promise.resolve(window.pywebview.api);
  }

  return new Promise((resolve, reject) => {
    const startedAt = Date.now();

    const check = () => {
      if (isDesktopApiReady()) {
        resolve(window.pywebview.api);
        return;
      }
      if (Date.now() - startedAt > 8000) {
        reject(new Error("Desktop bridge unavailable"));
        return;
      }
      window.setTimeout(check, 50);
    };

    window.addEventListener("pywebviewready", check, { once: true });
    check();
  });
};

const bridgeRoutes = {
  "/api/state": (bridge) => bridge.get_state(),
  "/api/view": (bridge, body) => bridge.set_view(body.view),
  "/api/monitoring/start": (bridge) => bridge.start_monitoring(),
  "/api/monitoring/stop": (bridge) => bridge.stop_monitoring(),
  "/api/monitoring/toggle": (bridge) => bridge.toggle_monitoring(),
  "/api/snooze": (bridge) => bridge.snooze(),
  "/api/resume-alerts": (bridge) => bridge.resume_alerts(),
  "/api/pause-toggle": (bridge) => bridge.toggle_pause(),
  "/api/settings": (bridge, body) => bridge.save_settings(body),
  "/api/settings/reset": (bridge) => bridge.reset_settings(),
  "/api/profile/sensitivity": (bridge, body) => bridge.save_sensitivity(body.measurement, body.value),
  "/api/voice/test": (bridge, body) => bridge.test_voice(body.personality, body.voice),
  "/api/voice/generate": (bridge, body) => bridge.generate_custom_voice(body.voice_description, body.voice_server_url),
  "/api/voice/generate-test": (bridge, body) => bridge.generate_custom_voice_test(body.voice_description, body.voice_server_url),
  "/api/voice/test-cloned-voice": (bridge, body) => bridge.test_cloned_voice(body.character_description, body.voice_server_url),
  "/api/calibration/start": (bridge) => bridge.begin_calibration(),
  "/api/calibration/preview": (bridge) => bridge.start_calibration_preview(),
  "/api/calibration/capture": (bridge) => bridge.start_calibration_capture(),
  "/api/calibration/accept": (bridge) => bridge.accept_calibration(),
  "/api/calibration/recapture": (bridge) => bridge.recapture(),
  "/api/calibration/cancel": (bridge) => bridge.cancel_calibration(),
  "/api/calibration/delete": (bridge) => bridge.delete_calibration(),
  "/frame/monitor": (bridge) => bridge.latest_monitor_frame(),
  "/frame/calibration": (bridge) => bridge.latest_calibration_frame()
};

const api = async (path, body) => {
  const bridge = await waitForDesktopApi();
  const route = bridgeRoutes[path];
  if (!route) {
    throw new Error(`Unknown desktop API route: ${path}`);
  }
  return route(bridge, body || {});
};

const statusClasses = {
  Good: "text-emerald-500",
  Warning: "text-amber-500",
  Bad: "text-rose-500",
  "No Detection": "text-zinc-400"
};

function App() {
  const [state, setState] = useState(null);
  const [view, setView] = useState("dashboard");
  const [error, setError] = useState("");

  const refresh = async () => {
    const next = await api("/api/state");
    setError("");
    setState(next);
    setView((current) => next.view || (next.needsCalibration && current === "dashboard" ? "calibration" : current));
  };

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
    const id = window.setInterval(() => refresh().catch((err) => setError(err.message)), 600);
    return () => window.clearInterval(id);
  }, []);

  const call = async (path, body) => {
    setError("");
    try {
      const next = await api(path, body);
      setState(next);
      if (next.view) setView(next.view);
      return next;
    } catch (err) {
      setError(err.message);
      return null;
    }
  };

  const constants = state?.constants;
  const settings = state?.settings;

  useEffect(() => {
    document.documentElement.classList.toggle("dark", Boolean(settings?.dark_mode));
  }, [settings?.dark_mode]);

  if (!state) {
    return <div className="grid min-h-screen place-items-center bg-zinc-100 text-zinc-700 dark:bg-zinc-950 dark:text-zinc-200">Loading ProPosture...</div>;
  }

  return (
    <div className="app-shell h-screen overflow-hidden bg-zinc-100 text-zinc-950 dark:bg-zinc-950 dark:text-zinc-100">
      <div className="mx-auto flex h-screen w-full max-w-6xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <Header state={state} view={view} setView={setView} call={call} />
        {error ? <div className="mb-3 rounded-md border border-rose-300 bg-rose-50 px-4 py-2 text-sm text-rose-700 dark:border-rose-800 dark:bg-rose-950 dark:text-rose-200">{error}</div> : null}
        <main className="app-content-scroll min-h-0 flex-1 overflow-y-auto pr-1">
          {view === "dashboard" ? <Dashboard state={state} call={call} /> : null}
          {view === "calibration" ? <Calibration state={state} call={call} /> : null}
          {view === "settings" ? <SettingsView state={state} call={call} /> : null}
        </main>
        <footer className="py-3 text-center text-xs text-zinc-500 dark:text-zinc-500">{constants.privacyNote}</footer>
      </div>
    </div>
  );
}

function Header({ state, view, setView, call }) {
  const nav = [
    ["dashboard", Gauge, "Dashboard"],
    ["calibration", Camera, "Calibrate"],
    ["settings", Settings, "Settings"]
  ];
  return (
    <header className="mb-4 flex flex-col gap-3 border-b border-zinc-200 pb-3 dark:border-zinc-800 md:flex-row md:items-center md:justify-between">
      <div className="flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-teal-600 text-white shadow-sm">
          <Gauge size={22} />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-normal">ProPosture</h1>
          <div className="flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
            <span className={`h-2.5 w-2.5 rounded-full ${state.monitoring ? "pulse-teal-ring" : ""}`} style={{ backgroundColor: state.headerStatus.color }} />
            <span>{state.headerStatus.text}</span>
          </div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {nav.map(([key, Icon, label]) => (
          <button key={key} className={view === key ? "nav-button-active" : "nav-button"} onClick={() => { setView(key); call("/api/view", { view: key }); }}>
            <Icon size={16} />
            {label}
          </button>
        ))}
        <button className="icon-button" title={state.paused || state.snoozed ? "Resume alerts" : "Pause alerts"} onClick={() => call(state.paused || state.snoozed ? "/api/resume-alerts" : "/api/pause-toggle")}>
          {state.paused || state.snoozed ? <Play size={17} /> : <Pause size={17} />}
        </button>
      </div>
    </header>
  );
}

function Dashboard({ state, call }) {
  const previewOn = state.settings.show_camera_preview;
  const isGenVoice = state.isGeneratingVoice;
  const glass = state.settings.glassmorphism !== false;
  const isLive = previewOn && state.monitoring;

  return (
    <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <div className="space-y-4">
        {isGenVoice && (
          <div className="flex items-center gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
            <Loader2 size={18} className="animate-spin flex-shrink-0" />
            <span>Building custom voice audio files... Monitoring will be available once processing is complete.</span>
          </div>
        )}
        <Panel glass={glass}>
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div>
              <p className="label">Current Posture</p>
              <div className={`mt-2 text-6xl font-extrabold tracking-tight ${statusClasses[state.postureStatus] || "text-zinc-400"}`}>{state.postureStatus === "No Detection" ? "--" : state.postureStatus}</div>
              <p className="mt-2.5 text-sm text-zinc-500 dark:text-zinc-400">{state.postureDetail}</p>
            </div>
            <button
              className={`${state.monitoring ? "danger-button" : "primary-button"} w-full sm:w-auto shadow-sm`}
              disabled={isGenVoice && !state.monitoring}
              title={isGenVoice && !state.monitoring ? "Voice files are still being generated" : ""}
              onClick={() => call("/api/monitoring/toggle")}
            >
              {state.monitoring ? <Square size={18} /> : isGenVoice ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
              {state.monitoring ? "Stop Monitoring" : isGenVoice ? "Generating Voice..." : "Start Monitoring"}
            </button>
          </div>
        </Panel>

        <Panel glass={glass}>
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="label">Camera Preview</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Local annotated feed</p>
            </div>
            <Toggle checked={previewOn} onChange={(checked) => call("/api/settings", { show_camera_preview: checked })} />
          </div>
          <div className={`grid aspect-video place-items-center overflow-hidden rounded-xl bg-zinc-950 border transition-all duration-300 ${
            isLive ? "border-teal-500/80 pulse-teal-border" : "border-zinc-200 dark:border-zinc-800"
          }`}>
            {isLive ? <FramePreview kind="monitor" alt="Camera preview" /> : <Camera className="text-zinc-500" size={42} />}
          </div>
        </Panel>
      </div>

      <aside className="space-y-4">
        <Panel glass={glass}>
          <p className="label mb-3">Session Statistics</p>
          <div className="grid grid-cols-3 gap-3 lg:grid-cols-1">
            <Stat title="Time" value={state.session.elapsedLabel} glass={glass} />
            <Stat title="Alerts" value={state.session.alerts} glass={glass} />
            <Stat title="Best Streak" value={state.session.bestStreakLabel} glass={glass} />
          </div>
        </Panel>
        <Panel glass={glass}>
          <p className="label mb-3">Controls</p>
          <div className="grid gap-2">
            <button className="secondary-button justify-start pl-4" onClick={() => call("/api/snooze")}>
              <Pause size={18} className="text-teal-600" />
              Pause 15 min
            </button>
            <button className="secondary-button justify-start pl-4" onClick={() => call("/api/calibration/start")}>
              <RotateCcw size={18} className="text-teal-600" />
              Recalibrate
            </button>
            <button className="secondary-button justify-start pl-4" onClick={() => call("/api/view", { view: "settings" })}>
              <Settings size={18} className="text-teal-600" />
              Settings
            </button>
          </div>
        </Panel>
      </aside>
    </section>
  );
}

function Calibration({ state, call }) {
  const step = state.calibration.step;
  const constants = state.constants;
  const [countdownStart, setCountdownStart] = useState(null);
  const [countdownRemaining, setCountdownRemaining] = useState(3);
  const countdownActive = countdownStart !== null;
  const glass = state.settings.glassmorphism !== false;

  useEffect(() => {
    if (step !== 1 && countdownStart !== null) {
      setCountdownStart(null);
    }
  }, [step, countdownStart]);

  useEffect(() => {
    if (step !== 1 || countdownStart === null) {
      return undefined;
    }

    setCountdownRemaining(3);
    const id = window.setInterval(() => {
      const elapsedMs = Date.now() - countdownStart;
      const nextRemaining = Math.max(0, 3 - Math.floor(elapsedMs / 1000));
      setCountdownRemaining(nextRemaining);

      if (elapsedMs >= 3000) {
        window.clearInterval(id);
        setCountdownStart(null);
        call("/api/calibration/capture");
      }
    }, 100);

    return () => window.clearInterval(id);
  }, [step, countdownStart]);

  if (step === 0) {
    return (
      <section className="space-y-4">
        <Panel glass={glass}>
          <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
            <PostureDiagrams />
            <div>
              <p className="label">Baseline Setup</p>
              <h2 className="mt-2 text-2xl font-bold tracking-normal">Calibration teaches ProPosture your normal upright pose.</h2>
              <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-300">
                Before we turn on the camera, make sure your full face and both shoulders can be visible in the frame. The baseline captured here becomes the pose monitoring compares against.
              </p>
              <ul className="mt-4 space-y-2 text-sm text-zinc-700 dark:text-zinc-300">
                <li className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-teal-600" />
                  <span>Face the camera naturally with your chin level.</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-teal-600" />
                  <span>Keep both shoulders visible, relaxed, and uncropped.</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-teal-600" />
                  <span>Sit in the upright position you want to maintain while monitoring.</span>
                </li>
              </ul>
              <button className="primary-button mt-6 shadow-sm" onClick={() => call("/api/calibration/preview")}>
                <Camera size={18} />
                I'm Ready
              </button>
            </div>
          </div>
        </Panel>
      </section>
    );
  }

  if (step === 1) {
    return (
      <section className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <Panel glass={glass}>
            <p className="label">Camera Preview</p>
            <p className="mt-1 mb-3 text-sm text-zinc-600 dark:text-zinc-300">
              Adjust until your full face and both shoulders are visible. When your posture feels right, click Ready and hold still for the countdown.
            </p>
            <div className="relative grid aspect-video place-items-center overflow-hidden rounded-xl border border-zinc-200 bg-zinc-950 dark:border-zinc-800">
              <FramePreview kind="calibration" alt="Calibration preview" />
              {countdownActive ? (
                <div className="absolute inset-0 grid place-items-center bg-zinc-950/70 text-white backdrop-blur-md transition-all duration-300">
                  <div className="text-center">
                    <div className="text-7xl font-extrabold tracking-tight tabular-nums animate-pulse">{Math.max(1, countdownRemaining)}</div>
                    <div className="mt-2 text-xs font-bold uppercase tracking-wider">Hold Still</div>
                  </div>
                </div>
              ) : null}
            </div>
            <button className="primary-button mt-4 disabled:cursor-not-allowed disabled:opacity-50 shadow-sm" disabled={countdownActive} onClick={() => setCountdownStart(Date.now())}>
              <Check size={18} />
              {countdownActive ? "Starting Capture..." : "Ready"}
            </button>
          </Panel>
          <Panel glass={glass}>
            <p className="label mb-3">Measurements</p>
            <MeasurementTable constants={constants} measurements={state.calibration.measurements} />
          </Panel>
        </div>
      </section>
    );
  }

  if (step === 2) {
    return (
      <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Panel glass={glass}>
          <p className="label mb-3">Capturing Baseline</p>
          <div className="grid aspect-video place-items-center overflow-hidden rounded-xl border border-zinc-200 bg-zinc-950 dark:border-zinc-800">
            <FramePreview kind="calibration" alt="Capture preview" />
          </div>
          <Progress label="Capture" value={state.calibration.captureProgress} />
        </Panel>
        <Panel glass={glass}>
          <p className="label">Hold Still</p>
          <div className="mt-4 text-5xl font-extrabold tracking-tight">{Math.round(state.calibration.captureProgress * 100)}%</div>
        </Panel>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <Panel glass={glass}>
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="label">Calibration Complete</p>
            <h2 className={`mt-2 text-2xl font-bold tracking-normal ${state.calibration.quality?.isAcceptable ? "text-emerald-500" : "text-amber-500"}`}>
              {state.calibration.quality?.isAcceptable ? "Capture quality is good." : "Some measurements varied during capture."}
            </h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="primary-button shadow-sm" onClick={() => call("/api/calibration/accept")}>
              <Check size={18} />
              Accept Baseline
            </button>
            <button className="secondary-button" onClick={() => call("/api/calibration/recapture")}>
              <RotateCcw size={18} />
              Recapture
            </button>
          </div>
        </div>
        <QualityTable constants={constants} quality={state.calibration.quality} />
      </Panel>
    </section>
  );
}

function SettingsView({ state, call }) {
  const constants = state.constants;
  const settings = state.settings;
  const profile = state.profile;
  const voiceOptions = Object.entries(constants.voices);
  const voiceModeOptions = Object.entries(constants.voiceModes);

  const [voiceDesc, setVoiceDesc] = useState(settings.voice_description || "");
  const [serverUrl, setServerUrl] = useState(settings.voice_server_url || "http://localhost:5123");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [voiceSourceType, setVoiceSourceType] = useState(settings.voice_source_type || "description");
  const [audioFile, setAudioFile] = useState(null);
  const [characterDesc, setCharacterDesc] = useState(settings.character_description || "");
  const [testStatus, setTestStatus] = useState("idle");
  const [activeTab, setActiveTab] = useState("voice");

  const isCustom = settings.voice_mode === "custom";
  const glass = settings.glassmorphism !== false;

  const tabs = [
    { id: "voice", label: "Voice", icon: Mic },
    { id: "posture", label: "Posture", icon: SlidersHorizontal },
    { id: "appearance", label: "Surface", icon: Camera },
    { id: "actions", label: "System", icon: MonitorStop },
  ];

  const waitForVoicePlayback = async () => {
    for (let i = 0; i < 200; i += 1) {
      const freshState = await api("/api/state");
      if (freshState?.voiceManagerSpeaking) {
        setTestStatus("playing");
      }
      if (freshState?.voiceManagerSpeaking === false && i > 5) {
        break;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 50));
    }
  };

  const readAudioFile = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      const bytes = new Uint8Array(event.target.result);
      let binary = "";
      for (let i = 0; i < bytes.length; i += 1) {
        binary += String.fromCharCode(bytes[i]);
      }
      resolve(btoa(binary));
    };
    reader.onerror = () => reject(new Error("Failed to read audio file"));
    reader.readAsArrayBuffer(file);
  });

  const handleTestVoice = async () => {
    if (voiceSourceType === "description") {
      await call("/api/settings", {
        voice_description: voiceDesc,
        voice_server_url: serverUrl,
        voice_mode: "custom",
        voice_source_type: "description",
      });

      setTesting(true);
      setTestStatus("generating");
      setTestResult(null);
      try {
        await call("/api/voice/generate-test", {
          voice_description: voiceDesc,
          voice_server_url: serverUrl,
        });
        await waitForVoicePlayback();
        setTestResult({ status: "complete" });
        setTestStatus("idle");
      } catch (err) {
        setTestResult({ error: err.message });
        setTestStatus("idle");
      } finally {
        setTesting(false);
      }
    } else {
      // Audio upload mode
      if (!audioFile && !settings.audio_file_name) {
        setTestResult({ error: "Please select an audio file" });
        return;
      }

      setTesting(true);
      setTestStatus("generating");
      setTestResult(null);

      try {
        const settingsUpdate = {
          voice_mode: "custom",
          voice_source_type: "audio",
          character_description: characterDesc,
          voice_server_url: serverUrl,
        };

        if (audioFile) {
          settingsUpdate.audio_file_data = await readAudioFile(audioFile);
          settingsUpdate.audio_file_name = audioFile.name;
        }

        await call("/api/settings", settingsUpdate);
        await call("/api/voice/test-cloned-voice", {
          character_description: characterDesc,
          voice_server_url: serverUrl,
        });
        await waitForVoicePlayback();
        setTestResult({ status: "complete" });
        setTestStatus("idle");
      } catch (err) {
        setTestResult({ error: err.message });
        setTestStatus("idle");
      } finally {
        setTesting(false);
      }
    }
  };

  return (
    <section className="settings-shell">
      <div className="settings-rail">
        <div className="settings-rail-mark">
          <span />
        </div>
        <div className="settings-tabs" role="tablist" aria-label="Settings sections">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveTab(tab.id)}
                className={`settings-tab ${isActive ? "settings-tab-active" : ""}`}
              >
                <Icon size={18} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="settings-content">
        {activeTab === "voice" && (
          <div className="settings-grid">
            <Panel glass={glass} className="settings-card-primary">
              <SectionTitle icon={Mic} title="Voice System" />

              <Field label="Voice Mode">
                <select className="input" value={settings.voice_mode} onChange={(e) => call("/api/settings", { voice_mode: e.target.value })}>
                  {voiceModeOptions.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                </select>
              </Field>

              {!isCustom ? (
                <Field label="gTTS Voice">
                  <div className="flex gap-2">
                    <select className="input" value={settings.tts_voice} onChange={(e) => call("/api/settings", { tts_voice: e.target.value })}>
                      {voiceOptions.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                    </select>
                    <button className="icon-button flex-shrink-0" title="Test voice" onClick={() => call("/api/voice/test", { personality: settings.coach_personality, voice: settings.tts_voice })}>
                      <Volume2 size={18} />
                    </button>
                  </div>
                </Field>
              ) : (
                <>
                  <Field label="Voice Source">
                    <select className="input" value={voiceSourceType} onChange={(e) => setVoiceSourceType(e.target.value)}>
                      <option value="description">Text Description</option>
                      <option value="audio">Upload Audio File</option>
                    </select>
                  </Field>

                  {voiceSourceType === "description" ? (
                    <Field label="Voice Description">
                      <textarea
                        id="voice-description-input"
                        className="input min-h-[120px] resize-y"
                        placeholder="A warm, focused coach with a calm tone and clear pace."
                        value={voiceDesc}
                        onChange={(e) => setVoiceDesc(e.target.value)}
                        onBlur={() => call("/api/settings", { voice_description: voiceDesc })}
                      />
                    </Field>
                  ) : (
                    <>
                      <Field label="Audio File">
                        {settings.audio_file_name ? (
                          <div className="mb-2 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
                            <div className="font-semibold">Current file: {settings.audio_file_name}</div>
                          </div>
                        ) : null}
                        <input
                          id="audio-file-input"
                          className="input"
                          type="file"
                          accept="audio/*"
                          onChange={(e) => setAudioFile(e.target.files?.[0] || null)}
                        />
                      </Field>

                      <Field label="Character Description">
                        <textarea
                          id="character-description-input"
                          className="input min-h-[120px] resize-y"
                          placeholder="A confident coach with steady cadence and direct encouragement."
                          value={characterDesc}
                          onChange={(e) => setCharacterDesc(e.target.value)}
                          onBlur={() => call("/api/settings", { character_description: characterDesc })}
                        />
                      </Field>
                    </>
                  )}
                </>
              )}
            </Panel>

            <Panel glass={glass} className="settings-card-secondary">
              <SectionTitle icon={Volume2} title="Output" />

              {isCustom ? (
                <Field label="Voice Server URL">
                  <input
                    id="voice-server-url-input"
                    className="input"
                    type="text"
                    placeholder="http://localhost:5123"
                    value={serverUrl}
                    onChange={(e) => setServerUrl(e.target.value)}
                    onBlur={() => call("/api/settings", { voice_server_url: serverUrl })}
                  />
                </Field>
              ) : null}

              <div className="mt-5">
                {isCustom ? (
                  testing ? (
                    <div className="flex min-h-12 items-center justify-center gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
                      <Loader2 size={20} className="flex-shrink-0 animate-spin" />
                      <span>{testStatus === "generating" ? "Generating test audio..." : "Playing back voice test"}</span>
                    </div>
                  ) : (
                    <button
                      id="test-voice-button"
                      className="primary-button w-full disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={voiceSourceType === "description" ? !voiceDesc.trim() : (!audioFile && !settings.audio_file_name) || !characterDesc.trim()}
                      onClick={handleTestVoice}
                    >
                      <Volume2 size={18} />
                      Test Voice
                    </button>
                  )
                ) : (
                  <button className="secondary-button w-full" onClick={() => call("/api/voice/test", { personality: settings.coach_personality, voice: settings.tts_voice })}>
                    <Volume2 size={18} />
                    Test Voice
                  </button>
                )}

                {testResult ? (
                  <div className={`mt-3 rounded-lg border px-3 py-2 text-sm ${
                    testResult.error
                      ? "border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-800 dark:bg-rose-950 dark:text-rose-200"
                      : "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
                  }`}>
                    {testResult.error ? `Error: ${testResult.error}` : "Test audio generated and played."}
                  </div>
                ) : null}
              </div>

              <div className="mt-6 border-t border-zinc-200/60 pt-5 dark:border-zinc-800/60">
                <Slider label="Volume" value={settings.volume} suffix="%" range={constants.ranges.volume} format={(value) => Math.round(value * 100)} onChange={(value) => call("/api/settings", { volume: value })} />
              </div>

            </Panel>
          </div>
        )}

        {activeTab === "posture" && (
          <div className="settings-grid">
            <Panel glass={glass} className="settings-card-primary">
              <SectionTitle icon={SlidersHorizontal} title="Alert Timing" />
              <div className="grid gap-8">
                <Slider label="Bad Posture Time" value={settings.alert_delay_sec} suffix="s" range={constants.ranges.alertDelay} onChange={(value) => call("/api/settings", { alert_delay_sec: value })} />
                <Slider label="Cooldown" value={settings.cooldown_sec} suffix="s" range={constants.ranges.cooldown} onChange={(value) => call("/api/settings", { cooldown_sec: value })} />
              </div>
            </Panel>

            <Panel glass={glass} className="settings-card-secondary">
              <SectionTitle icon={Gauge} title="Sensitivity" />
              {profile ? (
                <div className="grid gap-7">
                  {constants.measurements.map((measurement) => (
                    <Slider
                      key={measurement}
                      label={constants.measurementLabels[measurement]}
                      value={profile.sensitivity_multipliers[measurement] ?? constants.ranges.sensitivity.default}
                      range={constants.ranges.sensitivity}
                      onChange={(value) => call("/api/profile/sensitivity", { measurement, value })}
                    />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-zinc-500 dark:text-zinc-400">Calibrate before adjusting sensitivity.</p>
              )}
            </Panel>
          </div>
        )}

        {activeTab === "appearance" && (
          <div className="settings-grid">
            <Panel glass={glass} className="settings-card-primary">
              <SectionTitle icon={Camera} title="Camera" />
              <Field label="Camera Index">
                <select className="input" value={settings.camera_index} onChange={(e) => call("/api/settings", { camera_index: Number(e.target.value) })}>
                  {constants.cameraIndexes.map((index) => <option key={index} value={index}>{index}</option>)}
                </select>
              </Field>
            </Panel>

            <Panel glass={glass} className="settings-card-secondary">
              <SectionTitle icon={Settings} title="Surface" />
              <Field label="Theme">
                <select className="input" value={settings.dark_mode ? "dark" : "light"} onChange={(e) => call("/api/settings", { dark_mode: e.target.value === "dark" })}>
                  <option value="dark">Dark</option>
                  <option value="light">Light</option>
                </select>
              </Field>

              <div className="mt-5 flex min-h-14 items-center justify-between gap-3 border-t border-zinc-200/60 pt-5 dark:border-zinc-800/60">
                <div>
                  <span className="block text-sm font-semibold">Glass UI</span>
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">Frosted panels and translucent controls.</span>
                </div>
                <Toggle checked={settings.glassmorphism !== false} onChange={(checked) => call("/api/settings", { glassmorphism: checked })} />
              </div>

              <div className="mt-5 flex min-h-14 items-center justify-between gap-3 border-t border-zinc-200/60 pt-5 dark:border-zinc-800/60">
                <div>
                  <span className="block text-sm font-semibold">Launch at {constants.startupLabel}</span>
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">Start ProPosture automatically.</span>
                </div>
                <Toggle checked={settings.launch_at_startup} disabled={!constants.startupSupported} onChange={(checked) => call("/api/settings", { launch_at_startup: checked })} />
              </div>
            </Panel>
          </div>
        )}

        {activeTab === "actions" && (
          <div className="settings-grid">
            <Panel glass={glass} className="settings-card-primary">
              <SectionTitle icon={MonitorStop} title="System Actions" />
              <div className="grid gap-2">
                <button className="secondary-button justify-start" onClick={() => call("/api/settings/reset")}>
                  <RotateCcw size={18} className="text-teal-600" />
                  <span>Reset settings to default</span>
                </button>
                <button className="secondary-button justify-start" onClick={() => call("/api/calibration/start")}>
                  <Camera size={18} className="text-teal-600" />
                  <span>Recalibrate baseline</span>
                </button>
                <button className="danger-button justify-start" onClick={() => call("/api/calibration/delete")}>
                  <Trash2 size={18} />
                  <span>Delete calibration profile</span>
                </button>
              </div>
            </Panel>

            <Panel glass={glass} className="settings-card-secondary">
              <SectionTitle icon={Gauge} title="Status" />
              <div className="rounded-xl border border-zinc-200/70 bg-white/50 p-4 dark:border-zinc-800/60 dark:bg-zinc-950/40">
                <p className="text-sm font-semibold">{state.headerStatus.text}</p>
                <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{state.postureDetail}</p>
              </div>
            </Panel>
          </div>
        )}
      </div>
    </section>
  );
}

function Panel({ children, glass = true, className = "" }) {
  const baseClass = glass
    ? "glass-panel"
    : "border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900";
  return (
    <div className={`rounded-lg p-5 shadow-sm transition-all duration-300 ${baseClass} ${className}`}>
      {children}
    </div>
  );
}

function FramePreview({ kind, alt }) {
  const [src, setSrc] = useState("");

  useEffect(() => {
    let cancelled = false;
    const path = kind === "monitor" ? "/frame/monitor" : "/frame/calibration";

    const updateFrame = async () => {
      try {
        const frame = await api(path);
        if (!cancelled && frame) {
          setSrc(frame);
        }
      } catch {
        if (!cancelled) {
          setSrc("");
        }
      }
    };

    updateFrame();
    const id = window.setInterval(updateFrame, 150);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [kind]);

  if (!src) {
    return <Camera className="text-zinc-500" size={42} />;
  }

  return <img className="h-full w-full object-contain" src={src} alt={alt} />;
}

function Stat({ title, value, glass = true }) {
  const bgClass = glass
    ? "bg-white/40 dark:bg-zinc-900/40 border-zinc-200/60 dark:border-zinc-800/10"
    : "bg-zinc-50 dark:bg-zinc-950 border-zinc-200 dark:border-zinc-800";
  return (
    <div className={`rounded-lg border p-4 transition-all duration-200 hover:scale-[1.02] ${bgClass}`}>
      <div className="text-xs font-bold uppercase tracking-wider text-zinc-500">{title}</div>
      <div className="mt-2 text-2xl font-extrabold tracking-tight">{value}</div>
    </div>
  );
}

function SectionTitle({ icon: Icon, title }) {
  return (
    <div className="mb-4 flex items-center gap-2">
      <Icon size={18} className="text-teal-600" />
      <p className="label">{title}</p>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="mt-3 grid gap-2 text-sm">
      <span className="font-medium text-zinc-700 dark:text-zinc-300">{label}</span>
      {children}
    </label>
  );
}

function Slider({ label, value, suffix = "", range, format, onChange }) {
  const rounded = format ? format(value) : range.step < 1 ? Number(value).toFixed(1) : Math.round(value);
  return (
    <label className="grid gap-2 text-sm">
      <span className="flex items-center justify-between gap-3">
        <span className="font-medium text-zinc-700 dark:text-zinc-300">{label}</span>
        <span className="tabular-nums text-zinc-500">{rounded}{suffix}</span>
      </span>
      <input className="accent-teal-600" type="range" min={range.min} max={range.max} step={range.step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

function Toggle({ checked, disabled = false, onChange }) {
  return (
    <button disabled={disabled} className={`relative h-7 w-12 rounded-full transition ${checked ? "bg-teal-600" : "bg-zinc-300 dark:bg-zinc-700"} disabled:cursor-not-allowed disabled:opacity-50`} onClick={() => onChange(!checked)} title={checked ? "On" : "Off"}>
      <span className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition ${checked ? "left-6" : "left-1"}`} />
    </button>
  );
}

function Progress({ label, value }) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div className="mt-4">
      <div className="mb-1 flex justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="tabular-nums text-zinc-500">{pct}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
        <div className="h-full bg-teal-600 transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function MeasurementTable({ constants, measurements }) {
  return (
    <div className="space-y-2">
      {constants.measurements.map((name) => (
        <div key={name} className="flex items-center justify-between border-b border-zinc-200 py-2 text-sm last:border-0 dark:border-zinc-800">
          <span className="text-zinc-600 dark:text-zinc-400">{constants.measurementLabels[name]}</span>
          <span className="font-semibold tabular-nums">{measurements[name] === undefined ? "--" : measurements[name].toFixed(3)}</span>
        </div>
      ))}
    </div>
  );
}

function QualityTable({ constants, quality }) {
  const rows = useMemo(() => quality?.perMeasurement || {}, [quality]);
  if (!quality) return null;
  return (
    <div className="mt-6 overflow-hidden rounded-md border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-zinc-50 text-xs uppercase text-zinc-500 dark:bg-zinc-950">
          <tr>
            <th className="px-3 py-2">Measurement</th>
            <th className="px-3 py-2">Mean</th>
            <th className="px-3 py-2">Std Dev</th>
            <th className="px-3 py-2">Quality</th>
          </tr>
        </thead>
        <tbody>
          {constants.measurements.map((name) => (
            <tr key={name} className="border-t border-zinc-200 dark:border-zinc-800">
              <td className="px-3 py-2">{constants.measurementLabels[name]}</td>
              <td className="px-3 py-2 tabular-nums">{rows[name]?.mean.toFixed(3)}</td>
              <td className="px-3 py-2 tabular-nums">{rows[name]?.std.toFixed(3)}</td>
              <td className={rows[name]?.ok ? "px-3 py-2 text-emerald-500" : "px-3 py-2 text-amber-500"}>{rows[name]?.ok ? "Good" : "Review"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {quality.warnings.length ? <div className="border-t border-zinc-200 p-3 text-sm text-amber-600 dark:border-zinc-800 dark:text-amber-400">{quality.warnings.join(" ")}</div> : null}
    </div>
  );
}

function PostureDiagrams() {
  return (
    <div className="grid min-h-[260px] grid-cols-2 gap-3">
      <Figure good label="Good" detail="Full face and shoulders visible" />
      <Figure label="Bad" detail="Face or shoulders cropped" />
    </div>
  );
}

function Figure({ good = false, label, detail }) {
  return (
    <div className="flex flex-col items-center justify-end rounded-md border border-zinc-200 bg-zinc-50 px-3 pb-4 pt-4 dark:border-zinc-800 dark:bg-zinc-950">
      <span className={good ? "mb-2 text-sm font-bold text-emerald-500" : "mb-2 text-sm font-bold text-rose-500"}>{label}</span>
      <PoseIllustration good={good} />
      <span className="mt-3 min-h-10 text-center text-xs font-medium text-zinc-600 dark:text-zinc-400">{detail}</span>
    </div>
  );
}

function PoseIllustration({ good = false }) {
  const frameColor = good ? "#10b981" : "#ef4444";
  const frameFill = good ? "#ecfdf5" : "#fff1f2";
  const bodyFill = good ? "#ccfbf1" : "#fecdd3";
  const bodyStroke = good ? "#0f766e" : "#be123c";
  const clipId = good ? "pose-frame-good" : "pose-frame-bad";

  return (
    <svg className="h-40 w-full max-w-[220px]" viewBox="0 0 220 170" role="img" aria-label={good ? "Good camera framing" : "Bad camera framing"}>
      <defs>
        <clipPath id={clipId}>
          <rect x="20" y="14" width="180" height="128" rx="10" />
        </clipPath>
      </defs>
      <rect x="18" y="12" width="184" height="132" rx="12" fill={frameFill} stroke={frameColor} strokeWidth="4" />
      <path d="M18 78H202M110 12V144" stroke={good ? "#a7f3d0" : "#fecdd3"} strokeWidth="2" />
      {good ? (
        <>
          <path d="M58 140C66 116 84 102 110 102C136 102 154 116 162 140Z" fill={bodyFill} stroke={bodyStroke} strokeWidth="5" strokeLinejoin="round" />
          <path d="M98 100V84H122V100" fill={bodyFill} stroke={bodyStroke} strokeWidth="5" strokeLinejoin="round" />
          <circle cx="110" cy="62" r="27" fill="#fde68a" stroke={bodyStroke} strokeWidth="5" />
          <path d="M98 64C102 68 106 70 110 70C114 70 118 68 122 64" fill="none" stroke={bodyStroke} strokeLinecap="round" strokeWidth="4" />
          <path d="M63 118C91 125 129 125 157 118" fill="none" stroke={bodyStroke} strokeLinecap="round" strokeWidth="8" />
          <circle cx="42" cy="34" r="13" fill="#10b981" />
          <path d="M36 34L40 38L49 29" fill="none" stroke="#fff" strokeLinecap="round" strokeLinejoin="round" strokeWidth="4" />
        </>
      ) : (
        <>
          <g clipPath={`url(#${clipId})`}>
            <g transform="translate(64 0)">
              <path d="M58 140C66 116 84 102 110 102C136 102 154 116 162 140Z" fill={bodyFill} stroke={bodyStroke} strokeWidth="5" strokeLinejoin="round" />
              <path d="M98 100V84H122V100" fill={bodyFill} stroke={bodyStroke} strokeWidth="5" strokeLinejoin="round" />
              <circle cx="110" cy="62" r="27" fill="#fde68a" stroke={bodyStroke} strokeWidth="5" />
              <path d="M98 72C102 66 106 64 110 64C114 64 118 66 122 72" fill="none" stroke={bodyStroke} strokeLinecap="round" strokeWidth="4" />
            </g>
          </g>
          <circle cx="42" cy="34" r="13" fill="#ef4444" />
          <path d="M37 29L47 39M47 29L37 39" stroke="#fff" strokeLinecap="round" strokeWidth="4" />
        </>
      )}
    </svg>
  );
}

createRoot(document.getElementById("root")).render(<App />);
