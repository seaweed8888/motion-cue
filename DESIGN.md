# Desktop studio

Mode: Operate. Follow the user's three-column sketch. Build with native Qt Widgets
and QPainter; no browser shell or decorative bitmap assets.

Use a porcelain workspace (#F1F2F4), true-white instrument and health surfaces,
dark ink (#252629), secondary text (#676B72), and the PowerPoint orange family (#D35230, #C43E1C,
#B7472A) with pale peach selection surfaces (#FBECE5). Orange identifies actions,
active inference and telemetry, section wayfinding, and the tilt ball. Use tonal
layers, thin separators and generous central space. The instrument has one soft,
downward shadow and no outline; its pale recessed tilt field uses white-to-porcelain
tones. Keep the health ledger a clean white surface with crisp numeric values.
This follows Apple's foreground/background hierarchy and Google's tonal elevation
principle, without adding glass effects or changing the three-column arrangement.

References: [Apple materials](https://developer.apple.com/design/human-interface-guidelines/materials)
and [Google Material surfaces](https://developer.android.com/develop/ui/compose/designsystems/material3).

Use Segoe UI as the platform interface font, quiet 12px supporting copy,
15px section titles, and a 46px gesture label. Side panels scroll at short
window heights. The center grows with the window. Model and health values
must come from real state. Missing readings use an em dash.

The ball follows the newest accelerometer-derived roll and pitch over ±45 degrees
on a precise 16ms display clock, without positional easing or health-refresh delay.
The fading trail supplies visual continuity without delaying the ball itself.
The ball is gray without fresh telemetry and orange with live telemetry, with
a short fading orange trail while moving. The trail
clears on telemetry loss and fades within 550ms at rest. Without fresh telemetry
the ball recenters. It represents tilt, not position. Idle/other text is gray;
recognized gesture text uses the PowerPoint accent.
Keep keyboard focus visible and honor normal field editing. Avoid global letter
shortcuts that would interfere with user and session inputs.

No logo, invented app mark, or in-app header. Keep the normal native Windows
title bar and start maximized. The fullscreen action sits at the bottom of the
health panel; F11/Esc remain available. Remove filler and empty ready messages;
show real recording counts, errors and save confirmations only. Controls
are flat and lightly tinted; numeric fields have no exposed spin buttons but
retain keyboard stepping. Only the current recording actions are visible:
Record when ready, Stop/Discard while recording, Save/Discard during review.

The left inspector is gray while telemetry is inactive, and becomes a solid
PowerPoint-orange control surface when fresh device telemetry is live. Its
active treatment has white headings, peach-white fields and a white primary action.
Both side panels are 292px wide so the central tilt instrument is centered on
the window like a controller. Keep the right health ledger white and quiet.
The motion trail is a single tapered, fading ribbon, not overlapping dots.

Section headings use deep PowerPoint orange (#AE3B20) even in the default/offline
state, giving the quiet layout color and clear wayfinding. Headings on the powered
orange inspector remain white for contrast. This heading accent is independent
of connection state.

State color rule for readings and controls: gray means off, idle, disconnected, unavailable or disabled;
orange means active, connected, live, armed or recognized. Apply this to the
inspector, ball, gesture text, model readiness, status readouts and fullscreen
toggle. Static values remain neutral. Errors retain their separate red treatment.
