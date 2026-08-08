# implementation decisions

These decisions implement the preregistered research specification.

1. **Stateless logical randomness:** use Philox4x32-10 addressed by seed, stream, and
   logical index. This avoids call-order-dependent random streams.
2. **Explicit stage ordering:** require a causal stage in every scheduled task; do not
   infer venue equal-timestamp semantics.
3. **Separate receive and process tasks:** an order reaching the exchange does not imply
   instantaneous matching when exchange-processing latency is non-zero.
4. **Observer delivery at availability:** future policies may consume only delivered
   events, never pending or exchange-internal tasks.
5. **Hash full payloads:** replay traces use complete canonical event material rather
   than IDs alone.
6. **Truthful rejection state:** terminal cancel/replace failures are published with
   `AlreadyTerminal` and the actual terminal state; other rejection reasons remain non-terminal.
7. **No fee placeholder:** simulation kernel emits no fabricated zero-fee events; fee logic remains
   execution-metrics layer.
8. **No parallel scheduler:** correctness and determinism take priority; parallelism is
   considered only after profiling in performance analysis.
