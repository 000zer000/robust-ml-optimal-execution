# Step 17 — Tail-risk conventions

## Loss orientation

Implementation shortfall is oriented so that larger values are worse for both buy and sell parents. Tail statistics therefore operate directly on implementation-shortfall basis points as losses.

## Sample moments

For `n` completed and audited episodes:

- the mean uses all preregistered episodes;
- variance is the sample variance with denominator `n - 1`;
- standard deviation is the square root of that sample variance;
- the median is the middle observation or mean of the two middle observations.

No best-day, best-instrument, or best-seed filtering is permitted.

## Empirical VaR

For sorted losses `x_(1) <= ... <= x_(n)`, empirical VaR at level `alpha` uses nearest rank:

```text
VaR_alpha = x_(ceil(alpha * n))
```

This convention is frozen in the metric contract and cannot be changed after results are observed without a documented protocol amendment.

## Fractional empirical CVaR

CVaR uses the mean of exactly the worst `(1 - alpha) * n` empirical observations. If that tail mass is not an integer, the boundary observation receives the fractional weight required to make the exact tail mass.

For example, with 40 episodes at 95%, the tail mass is exactly two observations, so CVaR95 is the mean of the two largest losses. With 10 episodes at 95%, the tail mass is half an observation, so CVaR95 equals the largest loss rather than pretending five percent of ten creates a full second episode.

This is recorded as:

```text
fractional_worst_tail_mean
```

## Required outputs

Every aggregate report includes:

- episode count;
- mean;
- sample variance and standard deviation;
- minimum and maximum;
- median;
- VaR95 and CVaR95;
- VaR99 and CVaR99;
- mean and minimum completion;
- mean terminal-completion fraction;
- explicit quantile and CVaR method identifiers.

## Inference boundary

Step 17 provides descriptive empirical tail statistics. Dependence-aware confidence intervals and paired strategy inference remain governed by the frozen research protocol and are implemented in later statistical-analysis steps. The Step 17 fixture is not used to make a strategy claim.
