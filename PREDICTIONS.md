# Predictions for test 1, written before looking at its signals

I'm writing this before scoring test 1. Test 1 is the only run that hasn't influenced a design choice: test 2 was used to build the system, and test 3 was seen and then adjusted for (the design-log addendum in the notebook explains why). So test 1 is the real check, and every prediction below has to be one I can be clearly wrong about.

So far I've only looked at test 1's file names and the readme. No spectra, scores or features from test 1 have been computed.

---

## 1. What is frozen

Everything below stays exactly as it is in commit **`783a45b`** on `dev` (the notebook `triage_system.ipynb` plus `section7b_agent.py`). The only uncommitted change in the working tree is the `RUN_OFFSCOPE` flag in section 9, which turns off a test 2 API call and has no effect on the detector, the router or the agent. I'll commit this file on its own, and the result write-up will name that commit.

**Detector (sections 4c and 5c of the notebook).**
- VAE on the raw score, from P5, with the same architecture and training (60 epochs, latent 8).
- Both views are used: **absolute** (each bearing compared with its own baseline) and **relative** (each bearing compared with the median of the other three, Variant 4).
- Baseline: every snapshot in the first 24 hours, chosen by time.
- Thresholds from cross-fitting: 4 contiguous folds within the baseline, at q = 0.99 of the out-of-fold scores.
- Persistence K = 3 snapshots in a row.
- A "sustained" alarm is an episode that has lasted 36 snapshots (6 hours at 10-minute spacing).
- The distance baseline (z-distance with a 1-hour median) runs alongside as the simple comparison.

**Router v3 (section 6).** States are debounced, so a change counts only after it holds for 6 snapshots (`HOLD = 6`). While a bearing is in alarm it is rechecked every 6 hours (`RECHECK_H = 6`), and every bearing gets a periodic check every 12 hours (`PERIODIC_H = 12`).

**Agent (section 7, `section7b_agent.py`).**
- The system prompt, the five tools plus `submit_decision`, and the four fixes from P6's report are all unchanged:
  - the code writes the evidence list;
  - numbers are checked by value, and a rationale with ungrounded numbers is retried once and then blocked;
  - only the agent's own flags stick in memory;
  - a previously flagged bearing is never set back to normal.
- `gpt-4o-mini` at temperature 0, with `max_steps = 8`.
- `rule_baseline` stays the non-LLM comparison.

**The test 1 channel rule.** Only the first channel of each pair is used, columns 0, 2, 4 and 6, so the input matches tests 2 and 3, which have one channel per bearing.

If anything on this list changes after the first test 1 number appears, the run no longer counts as held out, and I'll say so in the write-up.

---

## 2. What we know about test 1 so far

**From the readme:**
- The run lasts from 12:06:24 on 2003-10-22 to 23:39:56 on 2003-11-25, with 2,156 files and 8 channels (two per bearing).
- At the end of the run there was an **inner-race defect on B3** and a **roller-element defect on B4**. B1 and B2 are not reported as failed.
- The readme doesn't say when either defect started. All we know is that both existed at the end.

**From the inventory (file names only, section 1 of the notebook):**
- The median spacing is 10 minutes, but 148 intervals are about 5 minutes.
- 44 of those 5-minute intervals fall within the first 24 hours. That's the readme's "first 43 files" and the reason the baseline is chosen by time, not by count.
- The other **117 short intervals come after the baseline**, and 107 of them are on Nov 20 alone. In those stretches, 36 snapshots cover less than 6 hours.
- The run has big holes in it, which I hadn't expected. The longest goes from 10:14 on Oct 23 to 14:39 on Oct 29, **6 days and 4 hours with no files**, and it begins within the last two hours of the baseline. In total, about 20 of the run's 34 days fall in gaps longer than an hour.
- After the baseline there are 2,000 snapshots, and the last 24 hours hold only 39.

**What the gaps do to the rules.** Every snapshot-count rule now covers an uneven amount of time:
- K = 3 and the 36-snapshot "sustained" rule;
- the 6-snapshot debounce and 1-hour median;
- the tool's "12 h ago", which is really "72 snapshots ago".

One 36-snapshot episode can stretch across a gap of several days. I'm not changing the rules for this, because that would mean tuning on test 1. Instead, every alarm time in the results will be reported with both its snapshot-count length and its wall-clock length.

---

## 3. Definitions, fixed now

Test 1 has no P6 result to take a cut-off from, so the cut-off below comes from the readme's end time alone, without looking at any signal.

- **Last file:** `2003-11-25 23:39:56`.
- **End-stage window:** the last 24 hours, from `2003-11-24 23:39:56` onwards. Anything there is reported on its own as end-stage. It doesn't count as early warning, and it doesn't count as false.
- **Early window:** after the baseline and before `2003-11-24 23:39:56`.
- **False alarm (detector):** a sustained alarm episode (36 snapshots) on **B1 or B2** that starts in the early window. Absolute and relative are counted separately.
- **False alert (agent):** an `alert` or `escalate` decision on **B1 or B2** in the early window. Consecutive alert or escalate decisions on the same bearing count as one **episode**. A `watch` on B1 or B2 isn't a false alert, because watch is the status the prompt gives to an absolute-only alarm, which it reads as likely rig-wide drift. I'll still report the count.
- **Early warning (agent):** the first `alert` or `escalate` on **B3 or B4** in the early window, with its lead time in hours before the last file.
- **Correct fault name:** `inner_race` on B3, `rolling_element` on B4. `unknown` and `rig_wide` are not wrong, but they aren't correct either.
- **Stricter or milder than the rules:** the agent's status compared with `rule_baseline` for the same decision, using normal < watch < alert < escalate, as in section 8.
- Alarms on B3 or B4 are never counted as false, whenever they happen, because we don't know when their defects began. That makes the B1/B2 false counts a lower bound on the false alarms, the same as on tests 2 and 3.

---

## 4. Predictions

Each prediction states the metric, what I expect, and what proves it wrong. Confidence is how sure I am now: high, medium or low.

**P1. Order of the relative alarms.**
- *Metric:* `first_6h_alarm` per bearing, for the relative VAE detector, in each of seeds 0, 1 and 2.
- *Expect:* at least one of B3 and B4 gets a sustained relative alarm before either B1 or B2 does (or B1 and B2 never get one), in **all three seeds**.
- *Why:* B3's median of the other three bearings is taken over B1, B2 and B4, so it is still the middle of two healthy bearings and one failing one. A median of three can tolerate one other failing bearing.
- *Wrong if:* in any seed, B1 or B2 gets a sustained relative alarm before both B3 and B4.
- *Confidence:* medium. On test 3, Variant 4 never alarmed on B3 and had 214 false episodes.

**P2. Both failing bearings show up as relative alarms.**
- *Metric:* whether B3 and B4 each have a `first_6h_alarm` (relative, seed 0).
- *Expect:* both do, at some point in the run, including the end-stage window.
- *Wrong if:* either has none.
- *Confidence:* low. If the two defects grow at about the same time, each one raises the median the other is compared with.

**P3. The absolute view drifts on the healthy bearings.**
- *Metric:* sustained absolute alarms on B1 and B2 in the early window (VAE, seed 0).
- *Expect:* at least one of B1 and B2 has one, probably soon after the 6-day gap ends on Oct 29.
- *Why:* I expect the rig to look different after the restart, just as test 3 drifted on all four bearings.
- *Wrong if:* neither B1 nor B2 has a sustained absolute alarm before the end-stage window.
- This is a prediction that a known weakness will show up again, not a hope.
- *Confidence:* medium.

**P4. The VAE against the distance baseline.**
- *Metric:* false sustained absolute episodes on B1 and B2 in the early window, VAE raw against distance with the 1-hour median, seed 0.
- *Expect:* the VAE has **at least as many** as the distance baseline, as it did on tests 2 and 3. So the VAE doesn't clearly earn its place on false alarms.
- *Wrong if:* the VAE has fewer.
- *Confidence:* medium.

**P5. The agent warns early on a failing bearing.**
- *Metric:* the first agent `alert` or `escalate` on B3 or B4.
- *Expect:* at least one, **24 hours or more before the last file**, so before `2003-11-24 23:39:56`.
- *Why:* that only happens if P1 holds or fault-frequency evidence passes z = 3 on B3 or B4, so P5 is only as good as P1.
- *Wrong if:* the first alert or escalate on B3 or B4 falls in the end-stage window, or there isn't one at all.
- *Confidence:* medium.

**P6. Fault naming is mostly `unknown`.**
- *Metric:* `suspected_fault` across the agent's alert and escalate decisions on B3 and B4.
- *Expect:* the correct name (`inner_race` on B3, `rolling_element` on B4) in **fewer than half** of those decisions, with `unknown` or `none` the most common label.
- *Why:* on test 2 the agent named B1's outer-race fault in 5 of its 20 decisions on B1. Of the other 15, 6 were `unknown` and 9 were `none`. Inner-race and rolling-element defects are usually harder to see in the envelope spectrum than outer-race ones, so I don't expect better.
- *Wrong if:* the correct name appears in half or more of them.
- I'll also count wrong specific names, such as `outer_race` on B3, because a confident wrong name is worse than `unknown`.
- *Confidence:* medium.

**P7. No false agent alerts on B1 and B2, even with drift.**
- *Metric:* false alert episodes on B1 and B2 (section 3), across all decisions made in the early window.
- *Expect:* **zero**.
- *Why:* if test 1 drifts the way test 3 did, all four bearings move together. Then B1 and B2 carry absolute alarms but no relative ones, the prompt sends them to `watch`, and P3's drift should produce many watch decisions and no alerts.
- *Wrong if:* there is one or more. That would mean a relative alarm or envelope evidence of z ≥ 3 fired on a healthy bearing. The `rule_baseline` column will show which.
- *Confidence:* low to medium. Test 3's 214 false relative episodes are the reason it isn't higher.

**P8. The agent is a little stricter than the rules, and never milder on a failing bearing.**
- *Metric:* the share of decisions that are stricter than `rule_baseline`, and the count of milder ones.
- *Expect:* stricter in **5–15%** of decisions, mostly on B3 and B4 recheck wake-ups (alert → escalate). Milder in **zero** decisions on B3 or B4 where the rules say alert or escalate.
- *Why:* on test 2 the agent was stricter in 7 of 66 decisions (11%), milder in none, and all 7 were B1 rechecks where it escalated past the rules' alert.
- *Wrong if:* stricter is above 25%, or any decision on B3 or B4 is milder than an alert or escalate from the rules. The second one matters more, because it's the unsafe direction.
- *Confidence:* medium.

**P9. The agent's mechanics hold up.**
- *Metric:* fallbacks (step limit), forced decisions, and decisions marked `agent_unverified`.
- *Expect:* zero fallbacks and at most one unverified decision. On test 2 all three counts were zero.
- *Wrong if:* there are any fallbacks, or two or more unverified decisions.
- *Confidence:* high.

**P10. Seed spread.**
- *Metric:* the min–max of `first_6h_alarm` across seeds 0–2, per bearing, for the relative VAE.
- *Expect:* within **6 hours** for B3 and B4, and the P1 verdict the same in all three seeds.
- *Wrong if:* the spread is larger than that, or P1 holds in some seeds and not others. On test 2, healthy bearings moved by up to 5 hours.
- *Confidence:* medium.

---

## 5. What counts as success, partial success and failure

These are set now, so the result can't be reframed afterwards. The question is the one test 3 failed on: **does the system give a warning on a failing bearing that can be told apart from the healthy ones, early enough to act on?**

**Success** needs all three of these:
1. P5 holds: the agent alerts or escalates on B3 or B4 at least 24 hours before the last file.
2. P7 holds: no false alert episodes on B1 or B2 in the early window.
3. P1 holds in all three seeds.

**Partial success:**
- A warning comes on B3 or B4 in the early window and comes before any B1 or B2 alert, but one of these is true:
  - there are 1 or 2 false alert episodes on B1 or B2; or
  - P1 holds in only one or two of the seeds.
- *Or* the warning on B3 or B4 falls only in the end-stage window and there are no false alerts at all. It's honest, but too late to plan maintenance.

**Failure:** any one of these.
- There is no alert or escalate on B3 or B4 at all.
- There are 3 or more false alert episodes on B1 or B2 in the early window.
- An alert on B1 or B2 comes **before** the first alert on B3 or B4. That's the same reasoning as test 3: a warning you can't tell from the false ones isn't a catch.

P2, P3, P4, P6, P8, P9 and P10 are reported prediction by prediction as right or wrong, but they don't change the verdict above. Whatever the verdict, no setting changes after test 1. If it fails, the write-up says why, and that is where the project ends. Nothing gets re-tuned on test 1.

---

## 6. Planned runs

1. **Spectra:** test 1 spectra from columns 0, 2, 4 and 6, using the same Welch → 128-band → shape-only code as tests 2 and 3.
2. **Detector, seeds 0, 1 and 2:**
   - `cross_fit(S1, t1, "test1", seed=s)`, saved as `cv_test1*.npz`;
   - `evaluate` and `evaluate_rel` for the VAE raw score and the distance baseline with the 1-hour median, absolute and relative, with `healthy_until = "2003-11-24 23:39:56"`.
   - `evaluate` takes one `failing` bearing, so I'll run it once with `failing=3` and once with `failing=4`, and count false episodes on B1 and B2 only.
   - Alarm times are reported as the **min–max range across seeds**, with the snapshot-count and wall-clock length of each episode.
3. **Envelope features:** P6's envelope features for test 1, computed with P6's code unchanged on the same four channels and saved as `data/derived/p6_test1_features.csv`. This file doesn't exist yet. It's computed once, before the agent run, and isn't looked at on its own.
4. **Router v3** on the seed 0 detector states.
5. **Agent:** run **once**, with seed 0, over every router wake-up, in time order.
   - Decisions are saved to `results/test1_decisions.csv` and the trace to `logs/test1_trace.jsonl`.
   - After that the run flag is set to `False`, so the notebook loads the saved results and doesn't call the API again.
   - Temperature 0 isn't perfectly repeatable, so a second run could differ. That's another reason to run it only once.
   - If the run breaks partway through (an API error, not a result I dislike), it's restarted from the start, and the restart is noted.
6. **Write-up:** a results section that goes through P1–P10 one at a time with each metric's value, marks each one right or wrong, and then gives the section 5 verdict.
