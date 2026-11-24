# Desktop dashboard review — 2026-11-24

Method: design review only (detector not applicable, native platform).
Target: `monitoring/dashboard.py`, Qt Widgets/QPainter on Windows.
Technical audit includes `monitoring/live.py` and the MQTT callback path.
User-authorized scope: critique, audit, harden and optimize loading and ball latency.

## Findings and changes

| Priority issue | Evidence before changes | Resolution |
|---|---|---|
| P1: delayed motion feedback | Motion waited for an 80ms health poll, then moved only 14% toward its target each 16ms frame. Prediction ran inside the telemetry lock on the MQTT callback. | Separate precise 16ms pose sampling; direct position updates; prediction outside the lock on a worker. The short ribbon supplies continuity without easing the ball. |
| P1: blocking model and recording operations | Model discovery/unpickling and JSON saves ran on the GUI thread. Save also held the telemetry lock during serialization and disk I/O. | Background discovery, loading and saving; commit model results on the GUI thread; serialize stopped takes outside the telemetry lock. Busy controls prevent duplicate operations. |

Prediction has one executing window and at most one waiting window. New windows
replace older waiting windows under overload; the health panel counts these as
Inference skips. All validated raw samples still reach recording. Model changes,
threshold changes and disconnects invalidate outstanding predictions. Results
older than two seconds are ignored. Prediction exceptions produce an error and
idle gesture without disconnecting healthy telemetry or invalidating recording.

Recording cannot start after a disconnect merely because the last sample was
recent. Failed saves retain the take. JSON is written to a `.json.partial` file
then renamed on completion, so training does not see a half-written `.json`.
Handled write failures remove the temporary file. Close waits for a pending save;
a failed save cancels the deferred close and allows retry. Fullscreen now restores
the preceding maximized/windowed state.

The display stops repainting after motion and its 550ms trail settle, and stops
its animation timer while hidden. Static instrument caching and a GPU rewrite
were not added: removing the measured scheduling/easing bottleneck achieved the
target without changing rendering infrastructure or adding dependencies.

## Measurements

Same machine, Python virtual environment, Qt Fusion/offscreen, 1440×900 window.
Seven synthetic telemetry injections per run. A 1ms event-loop probe measures
time from calling `receive()` to the ball position reaching 90% of a 45° step.
This measures desktop state response, not device-to-photon latency.

| Measurement | Before | After, final run |
|---|---:|---:|
| Median receive-to-ball-position response | 264.1ms | 12.2ms |
| Individual step responses | 268.4, 245.4, 264.1, 268.8, 246.4, 266.2, 244.4ms | 11.0, 10.5, 11.7, 13.8, 12.2, 14.8, 13.4ms |
| Fresh-process import + construct/show + process events | 653.8ms | 540.4ms |

An earlier after-change run measured 9.3ms median response and 641.1ms to the
first window. Startup includes module imports but excludes interpreter launch;
these are individual fresh-process runs with uncontrolled disk caches, not a
controlled cold-start speedup claim. The important loading change is that a saved
model no longer needs to finish loading before the window can respond.

The benchmark resets the ball to center, keeps the broker connected, injects
three validated 100Hz samples after a 23ms timer, and probes until x ≥ 0.9.
Input batches have contiguous device timestamps. No physical IMU, network or
display compositor is included. The 16ms Qt timer is best effort, not a real-time
scheduling guarantee. Batching, Wi-Fi/MQTT and display refresh add further delay.

## Design critique

Design specificity: authored for this controller. Equal side panels frame one
central instrument; orange identifies live state rather than decoration. The
instrument and health ledger remain clean white. No logo or header was added.
The ball remains gray offline, orange live, with a fading ribbon. Gesture labels
stay neutral for idle/other and orange for recognized gestures.

Overall impression: clear hierarchy and restrained controls. Responsive feedback
was the largest opportunity; it now follows the latest validated pose directly.

| Heuristic | Score / 4 | Assessment |
|---|---:|---|
| Visibility of system status | 3 | Broker, telemetry, model loading, recording and inference overload are visible. |
| Match with the real world | 4 | Roll/pitch, gesture names and sample counts match the instrument's job. |
| User control and freedom | 3 | Discard, cancel close, and fullscreen escape work; long worker calls cannot be cancelled. |
| Consistency and standards | 3 | Native title bar, focus and fields; consistent gray/orange semantics. |
| Error prevention | 3 | Validated telemetry/models, protected takes and disabled busy controls. |
| Recognition rather than recall | 3 | Settings and recording actions remain visible; threshold semantics require experience. |
| Flexibility and efficiency | 4 | Immediate motion path and nonblocking heavy work; threshold keyboard editing retained. |
| Aesthetic and minimalist design | 3 | Symmetric layout and clear focus; health ledger is dense. |
| Error recovery | 3 | Failed saves preserve data and permit retry; failed inference preserves collection. |
| Help and documentation | 2 | Tooltips and repository documentation exist; no in-window calibration guide. |
| Total | 31/40 | Good |

Cognitive load: moderate. Grouping and hierarchy work; simultaneous tuning and
collection controls plus a dense health ledger demand some familiarity. No extra
settings or introductory copy was added to the user's deliberately minimal UI.

Emotional journey: offline is quiet and truthful; connection provides orange
confirmation; direct ball movement gives immediate feedback; saved/failed take
messages protect confidence during collection.

Strengths: symmetrical instrument-first composition; redundant text and color
for connection states; only the current recording actions are visible.

Persona red flags: a first-time collector still needs to understand onset
thresholds and one-label-per-take recording. A power user can type/step thresholds
and leave fullscreen with Esc. A low-vision user needs a real Windows
screen-reader and display-scaling pass before accessibility can be certified.

Minor observations: long model filenames rely on the native combo popup;
supporting health text is compact. These do not justify replacing the layout.
The two priority issues above were addressed through optimize/harden; the final
polish check preserved the established palette, spacing and native controls.

Questions skipped: two priority issues; user already requested the associated fixes.

## Technical audit and validation

| Dimension | Result |
|---|---|
| Performance | Main measured delay removed; model and save work isolated from UI and telemetry locks. |
| Resilience | Bounded inference, stale-result rejection, failed prediction isolation, safe save/close behavior. |
| Appearance | Reviewed rendered offline/live states at 1440×900 and live state at 1100×768. Existing whites, trail and state colors preserved. |
| Native behavior | Maximized launch with title-bar controls, F11/Esc and scrollable side panels retained. |
| Accessibility/adaptivity | Existing accessible names and focus retained; actual screen-reader, Windows high-contrast and enlarged text not validated. |

94 tests pass, including C++ feature parity. Added coverage for direct motion
between health refreshes, slow model loading, a blocked predictor with concurrent
telemetry, bounded pending prediction, stale results after disconnect/model or
threshold changes, inference exceptions during recording, concurrent telemetry
during JSON save, failed/partial writes and deferred-close failure recovery.
Whitespace checks pass.

Limits: there is no physical IMU/MQTT latency measurement or real trained-model
benchmark here. Pose uses accelerometer tilt, so linear acceleration can disturb
it. Device batch size can dominate total delay. Background Python threads are
not hard real-time and cannot forcibly interrupt a model that never returns;
such a model occupies the single inference worker until it returns or the app
restarts. A process crash can leave a `.json.partial` file; training ignores it.
