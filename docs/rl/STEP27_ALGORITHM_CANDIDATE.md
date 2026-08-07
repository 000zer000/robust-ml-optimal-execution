# Step 27 — PPO algorithm candidate record

**Field:** `reinforcement_learning_algorithm`  
**Engineering candidate:** categorical PPO  
**Frozen research-field status:** unresolved  
**Reason not committed to `DECISIONS.md`:** `DECISIONS.md` belongs to the seven-file specification
lock, whose regeneration policy requires explicit approval of an amendment/resolution.

PPO was selected for the engineering gate before training results were inspected. The choice follows
the frozen requirement for one policy-gradient family and the finite discrete action contract. It is
not selected because of a positive Step 27 result; indeed, the engineering results retain cases in
which strong non-RL baselines are better on mean or tail cost.

Before final RL research activation, the project must explicitly resolve and lock this pre-data
field, resolve the final seed count (minimum ten), open Gate C, and rerun the complete exact
synthetic plus zero-shot historical protocol.
