# Design log

## 2026-11-26: Detector choice, fixed before test 3

Everything below was decided using test 2 only. Test 3 has not been scored yet, and nothing here will change once it is.

### Primary detector: VAE on the raw score

The primary detector is the VAE on the raw reconstruction score. Its threshold is the 99th percentile of cross-fitted scores from the baseline, and it alarms only after 3 snapshots in a row above that threshold.

- **It is P5's method, unchanged.** No part of the model or the score was changed to fit test 2.
- **It has the widest margin on test 2** between the failing bearing (B1) and the first sustained alarm on a healthy bearing. B1's sustained alarm starts on Feb 16 at 03:32. The earliest healthy-bearing alarm (B4) starts on Feb 17 at 03:52, about 24 hours later. The other variants in section 4c have margins of 14 to 19 hours.
- **It has the fewest moving parts.** There is no smoothing window to choose.

This choice costs something. On test 2 the VAE raw score has 3 false alarm episodes before the Feb 17 cut-off, against 1 for the distance baseline with the 1-hour median.

### Baseline detector: distance with the 1-hour median

The baseline is the z-distance from the baseline spectra, smoothed with a 1-hour rolling median. It is the simple alternative, and the VAE has to beat it on held-out data to justify being the primary detector.

### Settings fixed from now on

| Setting | Value |
|---|---|
| Baseline | first 24 hours of each run |
| Cross-fitting | 4 contiguous folds within the baseline |
| Threshold | q = 0.99 of the out-of-fold scores |
| Persistence | K = 3 snapshots in a row |
| "Sustained" alarm | an episode that lasts 6 hours |

None of these will change after test 3.

### Seed check (section 4d)

On test 2 the VAE was retrained with seeds 0, 1 and 2.

- **B1 does not move.** Its sustained alarm starts on Feb 16 at 03:32 with every seed.
- **The healthy bearings move.** The earliest healthy-bearing alarm (B4) moves between 02:32 and 03:52 on Feb 17, so the B1 margin ranges from 23 hours to about 24 hours 20 minutes. The ranking against the other variants holds with every seed.
- **B3 moves the most.** Its sustained alarm moves by almost 5 hours across seeds, from 07:22 to 12:12 on Feb 17.
- **False alarms barely change.** Episodes before the cut-off are 2 or 3, depending on the seed.

Because the healthy bearings move by up to 5 hours depending on the seed, VAE alarm times on test 3 will be reported as the range across seeds 0, 1 and 2, not as a single time.
