# Data

sample/continuous.json is explicitly synthetic, 100 Hz, with one simulated motion
and surrounding idle context. tests/fixtures/window.json is derived from it.
These verify mechanics, not sensor behavior. Raw/processed data is ignored.

Recording JSON carries user/session/recording IDs, acquisition timestamps,
sample_rate_hz, SI units, samples and labeled boundaries. See the
[training guide](../training/README.md).
Both partners must collect separate train/validation/test sessions and ordinary
handling; do not split windows from one recording across sets.
