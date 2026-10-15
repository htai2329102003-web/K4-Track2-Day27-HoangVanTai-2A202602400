# Reflection (≤1 page)

Fill this in before you submit.

**Which fault types were hardest to catch, and why?**

Subtle distribution and drift faults were the hardest because their measurements can remain close to the calibrated clean bounds. Missing-upstream lineage faults also required checking the expected edge count rather than merely checking whether the upstream list was empty. I combined exact structural checks for contracts and lineage with tuned statistical limits for amount distribution, freshness, runtime, embedding drift, and corpus age.

**What would you change about your cost/coverage tradeoff, if you had another pass?**

I would collect more clean-stream observations in `ctx.state` and use robust rolling estimates per signal. That could adapt thresholds to each stream while rejecting suspected faults from the reference window. The current solution makes one relevant metered call per event, which gives complete coverage within the private budget; repeated calls would add cost without adding independent evidence.
