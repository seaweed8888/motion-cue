# Documentation

Start with the [project README](../README.md) for installation, current status
and the dashboard launch command. [Agent instructions](../AGENTS.md) define
where future files belong.

## Component guides

Usage stays beside the component it describes.

| Guide | Covers |
|---|---|
| [Desktop and MQTT host](../monitoring/README.md) | Dashboard, local broker, recording controls and connections |
| [Recording and ML](../training/README.md) | Collection, segmentation, training, evaluation and export |
| [Firmware](../firmware/README.md) | ESP-IDF/EIM build, flash and remaining hardware integration |
| [Data](../data/README.md) | Recording format, synthetic fixtures and session boundaries |
| [Models](../models/README.md) | Training artifacts, evaluation outputs and release status |

## Reference

| Document | Covers |
|---|---|
| [MQTT protocol](reference/mqtt-protocol.md) | Topics, sessions, leases, events and raw telemetry |
| [Feature specification](reference/feature-spec.md) | SI units, 55-feature extraction and segmentation defaults |
| [Hardware decisions](reference/hardware.md) | Unknown board/IMU details and calibration requirements |
| [Product context](../PRODUCT.md) | Users, capabilities and product constraints; kept at the root for Impeccable |
| [Design context](../DESIGN.md) | Dashboard layout, palette and interaction rules; kept at the root for Impeccable |

## Reports and evidence

| Document | Covers |
|---|---|
| [Experiment log](reports/experiments.md) | Software verification and pending measured trials |
| [Dashboard performance review](reports/dashboard-performance.md) | UI critique, latency measurements and hardening checks from November 24, 2026 |

Design assets live in [mockups/](mockups/) and [previews/](previews/).
Tool-owned review snapshots stay in `.impeccable/critique/`; they are historical
records, not the current product specification.

## Archive

[Original project handoff](archive/handoff.md) preserves the November 23, 2026
planning document. Its proposed repository tree, toolchain and implementation
status are historical. Current instructions live in the project and component
READMEs above.
