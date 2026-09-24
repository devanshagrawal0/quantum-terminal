# Learning engine v2 — how the agent learns, and why v1 was wrong
2026-09-16. v1 (built 09-15) let the agent close a whole strategy for five years after
40 losing trades. That is not learning, it is superstition with a database. This is
the redesign, grounded in what the agent literature actually found works.

## The six rules, each with the paper that earned it

1. **Never close a door — explore with decayed evidence (Thompson sampling).**
   Each setup (e.g. trend-long in DOWNTREND) has a belief: mean net result, how sure
   we are, how much evidence and how OLD it is. Old evidence fades (half-life ~90
   days). Before acting, the agent draws a random sample from that belief; a setup
   that has looked bad gets picked rarely, never never. On top, a 10% exploration
   floor at half size — "probation trades" — keeps the evidence alive. This is
   discounted / sliding-window Thompson sampling, the standard answer for bandits
   in changing environments (Trovò et al. 2020; Cavenaghi et al. 2021; Qi et al.
   2023), applied to portfolio choice in "Bandit Networks" (2024/25).
   v1's failure was exactly the textbook failure these fix.

2. **Grade against a baseline, not raw.** A long that made +3% in a week where the
   whole market made +6% is a bad call. Every experience stores net result AND
   excess over the universe's average move over the same window. Lessons and
   evidence use the excess. (validate_reversal.py already residualises; the
   simulator now does too.)

3. **Learn everything a closed trade can teach, not just win/lose.** At close the
   simulator has the whole price path, so it computes the counterfactuals that are
   knowable then: max favourable / adverse excursion, and what the SAME trade would
   have returned with each of 3 stops × 3 targets, and the opposite side. A lesson
   that says "stopped out, then the target hit two days later — a 9% stop would
   have made +12%" teaches the risk plan, not just the direction. This is Dev's
   "learn whatever it can from the trade it makes", and it costs no model calls.

4. **Similar situations, by numbers, not by words.** Before deciding, for every coin
   on the table the engine finds the k most similar past situations (nearest
   neighbours on the standardised feature vector, same regime preferred) among
   experiences already closed, and shows their average excess result. The agent
   sees "in the 20 most similar situations, longs averaged −140 bps". ExpeL
   (Zhao et al. 2023) retrieves similar experiences as demonstrations; Generative
   Agents (Park et al. 2023) score memories by recency × relevance × importance.
   Here: relevance = feature distance, recency = decay, importance = |excess|.

5. **Insights have a lifecycle; they are never permanent and never unchecked.**
   ExpeL's mechanism: insights are ADDED, UPVOTED, DOWNVOTED, EDITED, and removed
   when their importance count hits zero. We add the quant gate from the plan
   (§11.7): an insight proposed by the model (or by the evidence engine) starts as
   `proposed`; it becomes `active` only after out-of-sample support — trades closed
   AFTER it was written agree with it (n ≥ 10, same sign); every later outcome that
   matches its condition upvotes or downvotes it; decayed disagreement retires it.
   An LLM can propose a rule; only the ledger can make it law.

6. **The reasoner states a probability and gets scored on it.** Every thesis carries
   a confidence. The record tallies win rate per confidence bucket (calibration).
   Overconfident buckets are shown back to the agent as a fact about itself. LLMs
   are known to be overconfident on high-probability calls (ForecastBench 2025);
   the only fix is to show them their own calibration.

## What stays from v1
The time-lock (a lesson is recallable only after its close date), the masked
observation, the hash-locked written-first discipline, the random control arm, and
the rule-agent twins that make every gain from "learning" measurable.

## What is deliberately NOT in v2
- Weight training. That is stage 3 (Trading-R1-style SFT + RL) and needs thousands
  of graded experiences from THIS engine first.
- News / causal chains. The engine learns from numbers today; the reasoner adds
  text when the news store is fixed. The lifecycle above is what will grade those
  theses too.

## Proof required before anyone trusts it
Same 6-year batch, same 60 coins, same costs: plain rule, random, v1 learner, v2
learner. v2 must (a) keep taking probation trades in every setup all six years, (b)
retire a bad skill when evidence turns, (c) beat the plain rule on excess-over-market
per trade with a t-stat, and (d) show a calibration table. If it fails (c) it is not
better, it is different.

Sources: ExpeL https://arxiv.org/abs/2308.10144 · Voyager https://arxiv.org/abs/2305.16291 ·
Generative Agents https://arxiv.org/abs/2304.03442 · Sliding-window TS (Trovò 2020)
https://www.researchgate.net/publication/341687161 · Discounted TS https://arxiv.org/pdf/2305.10718 ·
Bandit Networks for portfolios https://arxiv.org/abs/2410.04217 · Agentic Trading survey
https://arxiv.org/html/2605.19337v1 · ForecastBench https://arxiv.org/pdf/2409.19839
