import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowLeft,
  Camera,
  Check,
  Gauge,
  Mic,
  MonitorStop,
  Pause,
  Play,
  RotateCcw,
  Settings,
  SlidersHorizontal,
  Square,
  SunMoon,
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
    setState(next);
    setView((current) => next.needsCalibration && current === "dashboard" ? "calibration" : current);
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
    <div className="min-h-screen bg-zinc-100 text-zinc-950 dark:bg-zinc-950 dark:text-zinc-100">
      <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <Header state={state} view={view} setView={setView} call={call} />
        {error ? <div className="mb-3 rounded-md border border-rose-300 bg-rose-50 px-4 py-2 text-sm text-rose-700 dark:border-rose-800 dark:bg-rose-950 dark:text-rose-200">{error}</div> : null}
        <main className="min-h-0 flex-1">
          {view === "dashboard" ? <Dashboard state={state} call={call} /> : null}
          {view === "calibration" ? <Calibration state={state} call={call} setView={setView} /> : null}
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
        <div className="grid h-10 w-10 place-items-center rounded-md bg-teal-600 text-white shadow-sm">
          <Gauge size={22} />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-normal">ProPosture</h1>
          <div className="flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: state.headerStatus.color }} />
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
  return (
    <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <div className="space-y-4">
        <Panel>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="label">Current Posture</p>
              <div className={`mt-2 text-6xl font-bold tracking-normal ${statusClasses[state.postureStatus] || "text-zinc-400"}`}>{state.postureStatus === "No Detection" ? "--" : state.postureStatus}</div>
              <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">{state.postureDetail}</p>
            </div>
            <button className={state.monitoring ? "danger-button" : "primary-button"} onClick={() => call("/api/monitoring/toggle")}>
              {state.monitoring ? <Square size={18} /> : <Play size={18} />}
              {state.monitoring ? "Stop Monitoring" : "Start Monitoring"}
            </button>
          </div>
        </Panel>

        <Panel>
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="label">Camera Preview</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Local annotated feed</p>
            </div>
            <Toggle checked={previewOn} onChange={(checked) => call("/api/settings", { show_camera_preview: checked })} />
          </div>
          <div className="grid aspect-video place-items-center overflow-hidden rounded-md border border-zinc-200 bg-zinc-950 dark:border-zinc-800">
            {previewOn && state.monitoring ? <FramePreview kind="monitor" alt="Camera preview" /> : <Camera className="text-zinc-500" size={42} />}
          </div>
        </Panel>
      </div>

      <aside className="space-y-4">
        <Panel>
          <p className="label mb-3">Session Statistics</p>
          <div className="grid grid-cols-3 gap-2 lg:grid-cols-1">
            <Stat title="Time" value={state.session.elapsedLabel} />
            <Stat title="Alerts" value={state.session.alerts} />
            <Stat title="Best Streak" value={state.session.bestStreakLabel} />
          </div>
        </Panel>
        <Panel>
          <p className="label mb-3">Controls</p>
          <div className="grid gap-2">
            <button className="secondary-button" onClick={() => call("/api/snooze")}>
              <Pause size={18} />
              Pause 15 min
            </button>
            <button className="secondary-button" onClick={() => call("/api/calibration/start")}>
              <RotateCcw size={18} />
              Recalibrate
            </button>
            <button className="secondary-button" onClick={() => call("/api/view", { view: "settings" })}>
              <Settings size={18} />
              Settings
            </button>
          </div>
        </Panel>
      </aside>
    </section>
  );
}

function Calibration({ state, call, setView }) {
  const step = state.calibration.step;
  const constants = state.constants;

  if (step === 0) {
    return (
      <section className="space-y-4">
        <BackButton onClick={() => { call("/api/calibration/cancel"); setView("dashboard"); }} />
        <Panel>
          <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
            <PostureDiagrams />
            <div>
              <p className="label">Understanding Good Posture</p>
              <h2 className="mt-2 text-2xl font-bold tracking-normal">Set the baseline you want to maintain.</h2>
              <ul className="mt-4 space-y-2 text-sm text-zinc-700 dark:text-zinc-300">
                <li>Keep your head lifted at a natural height.</li>
                <li>Keep shoulders relaxed at your normal upright position.</li>
                <li>Sit back with a neutral spine.</li>
                <li>Place the screen at eye level.</li>
                <li>Keep feet flat on the floor.</li>
              </ul>
              <button className="primary-button mt-6" onClick={() => call("/api/calibration/preview")}>
                <Camera size={18} />
                Continue
              </button>
            </div>
          </div>
        </Panel>
      </section>
    );
  }

  if (step === 1) {
    const stable = state.calibration.stability >= constants.stabilityThreshold;
    return (
      <section className="space-y-4">
        <BackButton onClick={() => call("/api/calibration/cancel")} />
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <Panel>
            <p className="label mb-3">Camera Preview</p>
            <div className="grid aspect-video place-items-center overflow-hidden rounded-md border border-zinc-200 bg-zinc-950 dark:border-zinc-800">
              <FramePreview kind="calibration" alt="Calibration preview" />
            </div>
            <Progress label="Stability" value={state.calibration.stability} />
            <button className="primary-button mt-4 disabled:cursor-not-allowed disabled:opacity-50" disabled={!stable} onClick={() => call("/api/calibration/capture")}>
              <Check size={18} />
              Capture Baseline
            </button>
          </Panel>
          <Panel>
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
        <Panel>
          <p className="label mb-3">Capturing Baseline</p>
          <div className="grid aspect-video place-items-center overflow-hidden rounded-md border border-zinc-200 bg-zinc-950 dark:border-zinc-800">
            <FramePreview kind="calibration" alt="Capture preview" />
          </div>
          <Progress label="Capture" value={state.calibration.captureProgress} />
        </Panel>
        <Panel>
          <p className="label">Hold Still</p>
          <div className="mt-4 text-5xl font-bold">{Math.round(state.calibration.captureProgress * 100)}%</div>
        </Panel>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <Panel>
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="label">Calibration Complete</p>
            <h2 className={`mt-2 text-2xl font-bold tracking-normal ${state.calibration.quality?.isAcceptable ? "text-emerald-500" : "text-amber-500"}`}>
              {state.calibration.quality?.isAcceptable ? "Capture quality is good." : "Some measurements varied during capture."}
            </h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="primary-button" onClick={() => call("/api/calibration/accept")}>
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
  const coachOptions = Object.entries(constants.coachLabels);
  const voiceOptions = Object.entries(constants.voices);

  return (
    <section className="space-y-4">
      <BackButton onClick={() => call("/api/view", { view: "dashboard" })} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <SectionTitle icon={Mic} title="Voice" />
          <Field label="Coach Style">
            <select className="input" value={settings.coach_personality} onChange={(e) => call("/api/settings", { coach_personality: e.target.value })}>
              {coachOptions.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
          </Field>
          <Field label="gTTS Voice">
            <div className="flex gap-2">
              <select className="input" value={settings.tts_voice} onChange={(e) => call("/api/settings", { tts_voice: e.target.value })}>
                {voiceOptions.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select>
              <button className="icon-button" title="Test voice" onClick={() => call("/api/voice/test", { personality: settings.coach_personality, voice: settings.tts_voice })}>
                <Volume2 size={18} />
              </button>
            </div>
          </Field>
          <div className="mt-4">
            <Slider label="Volume" value={settings.volume} suffix="%" range={constants.ranges.volume} format={(value) => Math.round(value * 100)} onChange={(value) => call("/api/settings", { volume: value })} />
          </div>
        </Panel>

        <Panel>
          <SectionTitle icon={SlidersHorizontal} title="Alert Timing" />
          <Slider label="Bad Posture Time" value={settings.alert_delay_sec} suffix="s" range={constants.ranges.alertDelay} onChange={(value) => call("/api/settings", { alert_delay_sec: value })} />
          <Slider label="Cooldown" value={settings.cooldown_sec} suffix="s" range={constants.ranges.cooldown} onChange={(value) => call("/api/settings", { cooldown_sec: value })} />
        </Panel>

        <Panel>
          <SectionTitle icon={Camera} title="Camera" />
          <Field label="Camera Index">
            <select className="input" value={settings.camera_index} onChange={(e) => call("/api/settings", { camera_index: Number(e.target.value) })}>
              {constants.cameraIndexes.map((index) => <option key={index} value={index}>{index}</option>)}
            </select>
          </Field>
        </Panel>

        <Panel>
          <SectionTitle icon={SunMoon} title="Appearance & Startup" />
          <Field label="Theme">
            <select className="input" value={settings.dark_mode ? "dark" : "light"} onChange={(e) => call("/api/settings", { dark_mode: e.target.value === "dark" })}>
              <option value="dark">Dark</option>
              <option value="light">Light</option>
            </select>
          </Field>
          <div className="mt-4 flex items-center justify-between gap-3">
            <span className="text-sm font-medium">Launch at {constants.startupLabel}</span>
            <Toggle checked={settings.launch_at_startup} disabled={!constants.startupSupported} onChange={(checked) => call("/api/settings", { launch_at_startup: checked })} />
          </div>
        </Panel>
      </div>

      <Panel>
        <SectionTitle icon={Gauge} title="Posture Sensitivity" />
        {profile ? (
          <div className="grid gap-3 md:grid-cols-2">
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

      <Panel>
        <SectionTitle icon={MonitorStop} title="Actions" />
        <div className="flex flex-wrap gap-2">
          <button className="secondary-button" onClick={() => call("/api/settings/reset")}>
            <RotateCcw size={18} />
            Reset Defaults
          </button>
          <button className="secondary-button" onClick={() => call("/api/calibration/start")}>
            <Camera size={18} />
            Recalibrate
          </button>
          <button className="danger-button" onClick={() => call("/api/calibration/delete")}>
            <Trash2 size={18} />
            Delete Calibration
          </button>
        </div>
      </Panel>
    </section>
  );
}

function Panel({ children }) {
  return <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-panel dark:border-zinc-800 dark:bg-zinc-900">{children}</div>;
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

function Stat({ title, value }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-3 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="text-xs font-semibold uppercase text-zinc-500">{title}</div>
      <div className="mt-1 text-xl font-bold">{value}</div>
    </div>
  );
}

function BackButton({ onClick }) {
  return (
    <button className="secondary-button" onClick={onClick}>
      <ArrowLeft size={18} />
      Back to Dashboard
    </button>
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
    <div className="grid min-h-[260px] grid-cols-2 gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <Figure good label="Good" />
      <Figure label="Bad" />
    </div>
  );
}

function Figure({ good = false, label }) {
  return (
    <div className="relative flex items-end justify-center rounded-md bg-white dark:bg-zinc-900">
      <div className={good ? "figure figure-good" : "figure figure-bad"}>
        <span className="head" />
        <span className="spine" />
        <span className="shoulders" />
        <span className="hips" />
        <span className="leg left" />
        <span className="leg right" />
      </div>
      <span className={good ? "absolute top-3 text-sm font-bold text-emerald-500" : "absolute top-3 text-sm font-bold text-rose-500"}>{label}</span>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
