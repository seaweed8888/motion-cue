# MQTT protocol v1

One host, one device, prefix `motioncue/<device_id>/`. MQTT 3.1.1 clean sessions.
All control/events/status use QoS 0 and retain=false; no command replay or queues.
Lost events may be dropped rather than repeated. Firmware must serialize status
and events on one connection with a strictly increasing `seq` for the whole boot.
`boot_id` is a random unique boot token; reconnect starts disarmed.

Host publishes `control` every 400 ms:

```json
{"v":1,"device_id":"controller01","session":"random-host-session","lease":"random-pulse-token","command":null}
```

Commands replace null with `{"id":"unique-id","armed":true}` or false. Repeated
IDs apply once. A new session disarms first; host sends no arm until a live
disarmed acknowledgement. Firmware remembers the latest lease and echoes it.
Loss of pulses for 1200 ms or MQTT/Wi-Fi disconnect disarms and clears session.
Never apply buffered control frames following reconnect. Transport reconnect
must reset mode and subscription state. Only one host may own a device.

Device replies to pulses on `status`:

```json
{"v":1,"device_id":"controller01","boot_id":"random-boot","seq":1,"session":"random-host-session","lease":"random-pulse-token","armed":false,"online":true,"command_id":"","model_version":"v001","uptime_ms":12000}
```

`events` uses the same envelope, with `gesture` equal to `swipe_left`,
`swipe_right`, `twist` or `other`. Sequence is also the event deduplication ID.
Publish twist AFTER applying mode. Unknown movement and disarmed swipes never
cause keys. Host refuses events until status confirms the session and disarm.
Dashboard shows only acknowledged mode; pending commands suppress all swipes.
No host navigation queue exists. A processed disarm suppresses all later events;
an already executed OS key cannot be undone by a later disarm.

Freshness: host accepts only echoed random leases issued within the last 1200 ms
on its own monotonic clock. This bounds age without comparing device uptime to
wall time. Firmware must attach the lease at event generation, never update it
on a queued event. Host marks offline after 1500 ms without fresh status; resets
session on boot change, broker reconnect or heartbeat timeout. Retained status
is ignored. This protocol trusts the authenticated LAN broker, not arbitrary
publishers; use ACLs and TLS on networks that require it.

Telemetry is collection-only, at most 64 KiB per batch, nonretained. Envelope:
`v`, `device_id`, `boot_id`, `sample_rate_hz`, `units`, `samples`. Units and sample
rows match feature_spec.md. Batch at least 3 samples. Acquisition timestamps
must be strictly increasing across the entire recording. Collection must not
silently bridge restarts or sample loss; inspect timing gaps before training.
