# Historical queue-position claim boundary

Step 16 does not convert aggregate Binance L2 data into order-level history.

Permitted claims:

- passive fills are **estimated** under three declared queue assumptions;
- the central model allocates unexplained reductions proportionally;
- optimistic and pessimistic models form controlled sensitivity cases;
- exact FIFO is available only in synthetic exact mode;
- strategy conclusions are tested across queue assumptions.

Forbidden claims:

- exact historical queue position;
- exact historical FIFO fills;
- identification of cancellations ahead or behind;
- recovery of hidden liquidity;
- proof that the central assumption is realistic without empirical calibration;
- real-market profitability from ghost-agent replay.

Any table or figure using historical passive fills must include the queue-model identifier. The primary strategy comparison must be repeated under all three assumptions, and material ranking changes must be reported rather than averaged away.
