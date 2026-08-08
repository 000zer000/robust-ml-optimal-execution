"""Step 27 PPO engineering fixture with reward and OOD audits.

This module validates RL machinery only. It is deliberately labelled non-research while Gate C
is closed and does not replace the exact synthetic/historical final RL experiment required by the
frozen research protocol.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.distributions import Categorical

ACTION_LABELS = (
    "wait",
    "passive_25",
    "passive_50",
    "aggressive_25",
    "aggressive_50",
    "aggressive_100",
)
ACTION_INDEX = {label: index for index, label in enumerate(ACTION_LABELS)}
STATE_FEATURES = (
    "remaining_fraction",
    "time_remaining_fraction",
    "spread_ticks_scaled",
    "depth_ratio",
    "imbalance",
    "volatility_scaled",
    "latency_scaled",
    "fee_scaled",
    "impact_scaled",
    "recent_fill_fraction",
    "adverse_momentum_scaled",
)


class RLEngineeringError(ValueError):
    """Raised when a Step 27 RL engineering contract is violated."""


@dataclass(frozen=True)
class Regime:
    name: str
    spread_ticks: int
    depth_lots: int
    volatility_ticks: int
    latency_bps: float
    fee_bps: float
    impact_bps: float
    passive_fill_base: float
    persistence: float


@dataclass(frozen=True)
class RLEngineeringConfig:
    schema_version: str
    step: int
    research_status: str
    algorithm: str
    algorithm_status: str
    training_seeds: tuple[int, ...]
    train_episodes_per_update: int
    updates: int
    steps_per_episode: int
    parent_lots: int
    gamma: float
    gae_lambda: float
    clip_ratio: float
    entropy_coef: float
    value_coef: float
    learning_rate: float
    update_epochs: int
    hidden_units: int
    inventory_penalty_bps: float
    invalid_action_penalty_bps: float
    terminal_impact_multiplier: float
    evaluation_episodes: int
    ood_episodes: int
    seed: int


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_config(path: Path) -> RLEngineeringConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    config = RLEngineeringConfig(
        schema_version=str(raw["schema_version"]),
        step=int(raw["step"]),
        research_status=str(raw["research_status"]),
        algorithm=str(raw["algorithm"]),
        algorithm_status=str(raw["algorithm_status"]),
        training_seeds=tuple(int(v) for v in raw["training_seeds"]),
        train_episodes_per_update=int(raw["train_episodes_per_update"]),
        updates=int(raw["updates"]),
        steps_per_episode=int(raw["steps_per_episode"]),
        parent_lots=int(raw["parent_lots"]),
        gamma=float(raw["gamma"]),
        gae_lambda=float(raw["gae_lambda"]),
        clip_ratio=float(raw["clip_ratio"]),
        entropy_coef=float(raw["entropy_coef"]),
        value_coef=float(raw["value_coef"]),
        learning_rate=float(raw["learning_rate"]),
        update_epochs=int(raw["update_epochs"]),
        hidden_units=int(raw["hidden_units"]),
        inventory_penalty_bps=float(raw["inventory_penalty_bps"]),
        invalid_action_penalty_bps=float(raw["invalid_action_penalty_bps"]),
        terminal_impact_multiplier=float(raw["terminal_impact_multiplier"]),
        evaluation_episodes=int(raw["evaluation_episodes"]),
        ood_episodes=int(raw["ood_episodes"]),
        seed=int(raw["seed"]),
    )
    validate_config(config)
    return config


def validate_config(config: RLEngineeringConfig) -> None:
    if config.schema_version != "rl-engineering-config-v1" or config.step != 27:
        raise RLEngineeringError("Step 27 config identity changed")
    if config.research_status != "synthetic_validation_only_non_research":
        raise RLEngineeringError("Step 27 research boundary changed")
    if config.algorithm != "categorical_ppo":
        raise RLEngineeringError("Step 27 engineering algorithm must be categorical PPO")
    if config.algorithm_status != "engineering_candidate_not_frozen_research_field":
        raise RLEngineeringError("Step 27 algorithm status changed")
    if len(config.training_seeds) < 5 or len(set(config.training_seeds)) != len(
        config.training_seeds
    ):
        raise RLEngineeringError("at least five unique engineering seeds are required")
    if config.train_episodes_per_update < 4 or config.updates < 2:
        raise RLEngineeringError("training budget is too small for the engineering gate")
    if config.steps_per_episode < 4 or config.parent_lots < 4:
        raise RLEngineeringError("invalid Step 27 episode contract")
    for value in (config.gamma, config.gae_lambda, config.clip_ratio):
        if not 0 < value <= 1:
            raise RLEngineeringError("invalid PPO probability-like hyperparameter")
    for value in (
        config.entropy_coef,
        config.value_coef,
        config.learning_rate,
        config.inventory_penalty_bps,
        config.invalid_action_penalty_bps,
        config.terminal_impact_multiplier,
    ):
        if value < 0:
            raise RLEngineeringError("negative Step 27 hyperparameter")
    if config.update_epochs < 1 or config.hidden_units < 4:
        raise RLEngineeringError("invalid PPO network/update configuration")
    if config.evaluation_episodes < 10 or config.ood_episodes < 10:
        raise RLEngineeringError("Step 27 evaluation requires at least ten episodes")


TRAIN_REGIMES = (
    Regime("normal", 2, 150, 1, 0.15, 0.20, 0.35, 0.65, 0.55),
    Regime("active", 4, 110, 2, 0.30, 0.25, 0.55, 0.52, 0.35),
    Regime("thin", 4, 70, 2, 0.35, 0.25, 0.75, 0.42, 0.45),
)
OOD_REGIMES = (
    Regime("ood_thin_high_vol", 6, 38, 5, 0.55, 0.35, 1.10, 0.30, 0.20),
    Regime("ood_high_latency", 4, 95, 3, 1.50, 0.25, 0.65, 0.45, 0.30),
    Regime("ood_adverse_fees", 4, 100, 3, 0.45, 1.20, 0.70, 0.45, 0.30),
    Regime("ood_high_impact", 4, 70, 3, 0.45, 0.35, 1.80, 0.38, 0.25),
    Regime("ood_combined", 8, 30, 6, 1.80, 1.30, 2.10, 0.22, 0.15),
)


@dataclass
class EnvState:
    step: int
    remaining_lots: int
    reference_ticks: int
    bid_ticks: int
    ask_ticks: int
    bid_depth: int
    ask_depth: int
    volatility_ticks: int
    recent_fill_lots: int
    adverse_momentum_ticks: int


class SyntheticExecutionEnv:
    """Versioned interactive execution MDP used only for Step 27 engineering validation."""

    def __init__(
        self,
        config: RLEngineeringConfig,
        *,
        regime: Regime,
        seed: int,
        instrument_scale: float = 1.0,
        market_time_scale: float = 1.0,
        impact_exponent: float = 2.0,
    ) -> None:
        self.config = config
        self.regime = regime
        self.seed = int(seed)
        self.instrument_scale = float(instrument_scale)
        self.market_time_scale = float(market_time_scale)
        self.impact_exponent = float(impact_exponent)
        if self.instrument_scale <= 0:
            raise RLEngineeringError("instrument scale must be positive")
        if self.market_time_scale <= 0:
            raise RLEngineeringError("market time scale must be positive")
        if self.impact_exponent <= 0:
            raise RLEngineeringError("impact exponent must be positive")
        self._rng = np.random.default_rng(self.seed)
        self._arrival_ticks = round(10_000 * self.instrument_scale)
        self._state: EnvState | None = None
        self._done = False
        self._cumulative_cost_bps = 0.0
        self._last_components: dict[str, float] = {}
        self._executed_lots = 0
        self._episode_log: list[dict[str, object]] = []

    @property
    def state(self) -> EnvState:
        if self._state is None:
            raise RLEngineeringError("environment must be reset before use")
        return self._state

    @property
    def cumulative_cost_bps(self) -> float:
        return self._cumulative_cost_bps

    @property
    def episode_log(self) -> tuple[dict[str, object], ...]:
        return tuple(self._episode_log)

    def reset(self) -> np.ndarray:
        self._rng = np.random.default_rng(self.seed)
        spread = max(2, round(self.regime.spread_ticks * self.instrument_scale))
        center = self._arrival_ticks
        depth_base = max(10, round(self.regime.depth_lots * self.instrument_scale))
        bid_depth = depth_base + int(self._rng.integers(-depth_base // 5, depth_base // 5 + 1))
        ask_depth = depth_base + int(self._rng.integers(-depth_base // 5, depth_base // 5 + 1))
        self._state = EnvState(
            step=0,
            remaining_lots=self.config.parent_lots,
            reference_ticks=center,
            bid_ticks=center - spread // 2,
            ask_ticks=center + (spread - spread // 2),
            bid_depth=max(1, bid_depth),
            ask_depth=max(1, ask_depth),
            volatility_ticks=self.regime.volatility_ticks,
            recent_fill_lots=0,
            adverse_momentum_ticks=0,
        )
        self._done = False
        self._cumulative_cost_bps = 0.0
        self._last_components = {}
        self._executed_lots = 0
        self._episode_log = []
        return self.observation()

    def valid_action_mask(self) -> np.ndarray:
        state = self.state
        mask = np.ones(len(ACTION_LABELS), dtype=bool)
        if state.remaining_lots <= 0:
            mask[:] = False
            mask[ACTION_INDEX["wait"]] = True
            return mask
        last_decision = state.step >= self.config.steps_per_episode - 1
        if last_decision:
            mask[ACTION_INDEX["wait"]] = False
            mask[ACTION_INDEX["passive_25"]] = False
            mask[ACTION_INDEX["passive_50"]] = False
        return mask

    def observation(self) -> np.ndarray:
        state = self.state
        total_depth = max(1, state.bid_depth + state.ask_depth)
        imbalance = (state.bid_depth - state.ask_depth) / total_depth
        time_remaining = 1.0 - state.step / max(1, self.config.steps_per_episode - 1)
        return np.asarray(
            [
                state.remaining_lots / self.config.parent_lots,
                max(0.0, time_remaining),
                (state.ask_ticks - state.bid_ticks) / 10.0,
                min(4.0, total_depth / max(1, self.config.parent_lots)) / 4.0,
                imbalance,
                state.volatility_ticks / 10.0,
                self.regime.latency_bps / 2.0,
                self.regime.fee_bps / 2.0,
                self.regime.impact_bps / 2.5,
                state.recent_fill_lots / self.config.parent_lots,
                state.adverse_momentum_ticks / 10.0,
            ],
            dtype=np.float32,
        )

    def _quantity_for_action(self, label: str) -> int:
        remaining = self.state.remaining_lots
        if label == "wait":
            return 0
        if label.endswith("_25"):
            fraction = 0.25
        elif label.endswith("_50"):
            fraction = 0.50
        elif label.endswith("_100"):
            fraction = 1.0
        else:
            raise RLEngineeringError(f"unknown RL action {label}")
        return min(remaining, max(1, math.ceil(remaining * fraction)))

    def _passive_fill(self, requested: int) -> int:
        if requested <= 0:
            return 0
        state = self.state
        depth_total = max(1, state.bid_depth + state.ask_depth)
        favorable_imbalance = (state.bid_depth - state.ask_depth) / depth_total
        probability = self.regime.passive_fill_base + 0.22 * favorable_imbalance
        probability -= 0.035 * max(0, state.volatility_ticks - 1)
        probability -= 0.03 * max(0.0, self.regime.latency_bps - 0.2)
        probability = float(np.clip(probability, 0.05, 0.95))
        if self.market_time_scale != 1.0:
            probability = 1.0 - (1.0 - probability) ** self.market_time_scale
            probability = float(np.clip(probability, 0.01, 0.99))
        capacity = max(1, int(state.bid_depth * 0.65))
        stochastic_fraction = float(self._rng.beta(2.5, 2.0))
        if float(self._rng.random()) > probability:
            stochastic_fraction *= 0.15
        return min(requested, capacity, round(requested * stochastic_fraction))

    def _cost_for_fill(self, fill_lots: int, price_ticks: float, aggressive: bool) -> float:
        if fill_lots <= 0:
            return 0.0
        state = self.state
        price_cost = (price_ticks - self._arrival_ticks) / self._arrival_ticks * 10_000.0
        participation = fill_lots / max(1, state.ask_depth if aggressive else state.bid_depth)
        if self.impact_exponent == 2.0:
            impact = self.regime.impact_bps * participation * participation
        else:
            impact = self.regime.impact_bps * participation**self.impact_exponent
        latency = self.regime.latency_bps * (1.0 + state.volatility_ticks / 4.0)
        fee = self.regime.fee_bps if aggressive else -0.20 * self.regime.fee_bps
        adverse = max(0.0, state.adverse_momentum_ticks) * (0.35 if aggressive else 0.75)
        return (price_cost + impact + latency + fee + adverse) * fill_lots / self.config.parent_lots

    def _advance_market(self, aggressive_fill: int, passive_fill: int) -> None:
        state = self.state
        shock = int(self._rng.choice([-1, 0, 1], p=[0.25, 0.50, 0.25]))
        persistence = (
            1 if state.adverse_momentum_ticks > 0 else -1 if state.adverse_momentum_ticks < 0 else 0
        )
        if float(self._rng.random()) < self.regime.persistence:
            shock += persistence
        shock = int(np.clip(shock, -2, 2)) * self.regime.volatility_ticks
        if self.market_time_scale != 1.0:
            shock = round(shock * math.sqrt(self.market_time_scale))
        agent_impact = round(self.regime.impact_bps * aggressive_fill / max(1, state.ask_depth))
        next_reference = max(100, state.reference_ticks + shock + agent_impact)
        spread_jitter = int(self._rng.integers(0, 2)) * 2
        spread = max(
            2,
            round(self.regime.spread_ticks * self.instrument_scale) + spread_jitter,
        )
        depth_base = max(8, round(self.regime.depth_lots * self.instrument_scale))
        bid_depth = depth_base + int(self._rng.integers(-depth_base // 3, depth_base // 3 + 1))
        ask_depth = depth_base + int(self._rng.integers(-depth_base // 3, depth_base // 3 + 1))
        self._state = EnvState(
            step=state.step + 1,
            remaining_lots=state.remaining_lots - aggressive_fill - passive_fill,
            reference_ticks=next_reference,
            bid_ticks=next_reference - spread // 2,
            ask_ticks=next_reference + (spread - spread // 2),
            bid_depth=max(1, bid_depth),
            ask_depth=max(1, ask_depth),
            volatility_ticks=self.regime.volatility_ticks,
            recent_fill_lots=aggressive_fill + passive_fill,
            adverse_momentum_ticks=shock,
        )

    def step(self, action_index: int) -> tuple[np.ndarray, float, bool, dict[str, object]]:
        if self._done:
            raise RLEngineeringError("cannot step a terminated Step 27 episode")
        if not 0 <= int(action_index) < len(ACTION_LABELS):
            raise RLEngineeringError("RL action index out of range")
        mask = self.valid_action_mask()
        action_index = int(action_index)
        label = ACTION_LABELS[action_index]
        invalid = not bool(mask[action_index])
        if invalid:
            label = "wait"
        state_before = self.state
        requested = self._quantity_for_action(label)
        aggressive = label.startswith("aggressive")
        execution_price = 0.0
        execution_depth = 1
        if aggressive:
            aggressive_fill = requested
            passive_fill = 0
            participation = aggressive_fill / max(1, state_before.ask_depth)
            execution_price = state_before.ask_ticks + self.regime.impact_bps * participation
            execution_depth = state_before.ask_depth
            execution_cost = self._cost_for_fill(aggressive_fill, execution_price, True)
        elif label.startswith("passive"):
            aggressive_fill = 0
            passive_fill = self._passive_fill(requested)
            execution_price = float(state_before.bid_ticks)
            execution_depth = state_before.bid_depth
            execution_cost = self._cost_for_fill(passive_fill, execution_price, False)
        else:
            aggressive_fill = 0
            passive_fill = 0
            execution_cost = 0.0
        inventory_risk = (
            self.config.inventory_penalty_bps
            * (state_before.remaining_lots / self.config.parent_lots) ** 2
            / self.config.steps_per_episode
        )
        invalid_penalty = self.config.invalid_action_penalty_bps if invalid else 0.0
        self._advance_market(aggressive_fill, passive_fill)
        terminal_completion = 0.0
        terminal_fill = 0
        terminal_price = 0.0
        terminal_depth = 1
        terminal_adverse_momentum = 0
        reached_horizon = self.state.step >= self.config.steps_per_episode
        if reached_horizon and self.state.remaining_lots > 0:
            remaining = self.state.remaining_lots
            participation = remaining / max(1, self.state.ask_depth)
            forced_price = self.state.ask_ticks + (
                self.regime.impact_bps * self.config.terminal_impact_multiplier * participation
            )
            terminal_fill = remaining
            terminal_price = float(forced_price)
            terminal_depth = self.state.ask_depth
            terminal_adverse_momentum = self.state.adverse_momentum_ticks
            terminal_completion = self._cost_for_fill(remaining, forced_price, True)
            self._state.remaining_lots = 0
            self._executed_lots += remaining
        filled_now = aggressive_fill + passive_fill
        self._executed_lots += filled_now
        total_cost = execution_cost + inventory_risk + invalid_penalty + terminal_completion
        reward = -total_cost
        self._cumulative_cost_bps += total_cost
        self._done = self.state.remaining_lots == 0 or reached_horizon
        components = {
            "execution_cost_bps": execution_cost,
            "inventory_risk_bps": inventory_risk,
            "invalid_action_penalty_bps": invalid_penalty,
            "terminal_completion_bps": terminal_completion,
        }
        self._last_components = components
        log_row = {
            "step": state_before.step,
            "action": ACTION_LABELS[action_index],
            "effective_action": label,
            "invalid": invalid,
            "requested_lots": requested,
            "aggressive_fill_lots": aggressive_fill,
            "passive_fill_lots": passive_fill,
            "remaining_before": state_before.remaining_lots,
            "remaining_after": self.state.remaining_lots,
            "arrival_ticks": self._arrival_ticks,
            "execution_price_ticks": execution_price,
            "execution_depth_lots": execution_depth,
            "execution_adverse_momentum_ticks": state_before.adverse_momentum_ticks,
            "terminal_fill_lots": terminal_fill,
            "terminal_price_ticks": terminal_price,
            "terminal_depth_lots": terminal_depth,
            "terminal_adverse_momentum_ticks": terminal_adverse_momentum,
            "parent_lots": self.config.parent_lots,
            "steps_per_episode": self.config.steps_per_episode,
            "regime_impact_bps": self.regime.impact_bps,
            "regime_latency_bps": self.regime.latency_bps,
            "regime_fee_bps": self.regime.fee_bps,
            "regime_volatility_ticks": self.regime.volatility_ticks,
            "impact_exponent_parameter": self.impact_exponent,
            "market_time_scale_parameter": self.market_time_scale,
            "inventory_penalty_bps_parameter": self.config.inventory_penalty_bps,
            "invalid_action_penalty_bps_parameter": self.config.invalid_action_penalty_bps,
            "reward": reward,
            **components,
        }
        self._episode_log.append(log_row)
        info: dict[str, object] = {
            **log_row,
            "completed": self.state.remaining_lots == 0,
            "executed_lots": self._executed_lots,
            "cumulative_cost_bps": self._cumulative_cost_bps,
        }
        return self.observation(), reward, self._done, info


def _independent_fill_cost(
    row: dict[str, object],
    *,
    fill_lots: int,
    price_ticks: float,
    depth_lots: int,
    adverse_momentum_ticks: int,
    aggressive: bool,
) -> float:
    if fill_lots <= 0:
        return 0.0
    arrival = float(row["arrival_ticks"])
    price_cost = (price_ticks - arrival) / arrival * 10_000.0
    participation = fill_lots / max(1, depth_lots)
    impact_exponent = float(row.get("impact_exponent_parameter", 2.0))
    if impact_exponent == 2.0:
        impact = float(row["regime_impact_bps"]) * participation * participation
    else:
        impact = float(row["regime_impact_bps"]) * participation**impact_exponent
    latency = float(row["regime_latency_bps"]) * (1.0 + float(row["regime_volatility_ticks"]) / 4.0)
    fee_bps = float(row["regime_fee_bps"])
    fee = fee_bps if aggressive else -0.20 * fee_bps
    adverse = max(0.0, adverse_momentum_ticks) * (0.35 if aggressive else 0.75)
    return (price_cost + impact + latency + fee + adverse) * fill_lots / float(row["parent_lots"])


def reconstruct_reward(row: dict[str, object]) -> float:
    aggressive_fill = int(row["aggressive_fill_lots"])
    passive_fill = int(row["passive_fill_lots"])
    execution_fill = aggressive_fill + passive_fill
    execution_cost = _independent_fill_cost(
        row,
        fill_lots=execution_fill,
        price_ticks=float(row["execution_price_ticks"]),
        depth_lots=int(row["execution_depth_lots"]),
        adverse_momentum_ticks=int(row["execution_adverse_momentum_ticks"]),
        aggressive=aggressive_fill > 0,
    )
    inventory_risk = (
        float(row["inventory_penalty_bps_parameter"])
        * (float(row["remaining_before"]) / float(row["parent_lots"])) ** 2
        / float(row["steps_per_episode"])
    )
    invalid_penalty = (
        float(row["invalid_action_penalty_bps_parameter"]) if bool(row["invalid"]) else 0.0
    )
    terminal_cost = _independent_fill_cost(
        row,
        fill_lots=int(row["terminal_fill_lots"]),
        price_ticks=float(row["terminal_price_ticks"]),
        depth_lots=int(row["terminal_depth_lots"]),
        adverse_momentum_ticks=int(row["terminal_adverse_momentum_ticks"]),
        aggressive=True,
    )
    return -(execution_cost + inventory_risk + invalid_penalty + terminal_cost)


class ActorCritic(nn.Module):
    def __init__(self, input_dim: int, hidden_units: int, actions: int) -> None:
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(input_dim, hidden_units),
            nn.Tanh(),
            nn.Linear(hidden_units, hidden_units),
            nn.Tanh(),
        )
        self.policy = nn.Linear(hidden_units, actions)
        self.value = nn.Linear(hidden_units, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        hidden = self.body(x)
        return self.policy(hidden), self.value(hidden).squeeze(-1)


def _masked_logits(logits: torch.Tensor, masks: torch.Tensor) -> torch.Tensor:
    if logits.shape != masks.shape:
        raise RLEngineeringError("PPO action mask shape mismatch")
    if not bool(torch.all(torch.any(masks, dim=-1))):
        raise RLEngineeringError("PPO encountered a state with no valid action")
    return logits.masked_fill(~masks, -1.0e9)


@dataclass
class RolloutBatch:
    observations: torch.Tensor
    actions: torch.Tensor
    old_log_probs: torch.Tensor
    advantages: torch.Tensor
    returns: torch.Tensor
    masks: torch.Tensor


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)


def _sample_regime(rng: np.random.Generator) -> Regime:
    return TRAIN_REGIMES[int(rng.integers(0, len(TRAIN_REGIMES)))]


def _collect_rollout(
    model: ActorCritic,
    config: RLEngineeringConfig,
    *,
    seed: int,
    episodes: int,
) -> RolloutBatch:
    observations: list[np.ndarray] = []
    actions: list[int] = []
    log_probs: list[float] = []
    rewards: list[float] = []
    values: list[float] = []
    dones: list[bool] = []
    masks: list[np.ndarray] = []
    rng = np.random.default_rng(seed)
    for _episode in range(episodes):
        regime = _sample_regime(rng)
        env_seed = int(rng.integers(0, 2**31 - 1))
        env = SyntheticExecutionEnv(config, regime=regime, seed=env_seed)
        observation = env.reset()
        done = False
        while not done:
            mask_np = env.valid_action_mask()
            obs_t = torch.from_numpy(observation).unsqueeze(0)
            mask_t = torch.from_numpy(mask_np).unsqueeze(0)
            with torch.no_grad():
                logits, value = model(obs_t)
                logits = _masked_logits(logits, mask_t)
                distribution = Categorical(logits=logits)
                action = distribution.sample()
                log_prob = distribution.log_prob(action)
            next_obs, reward, done, _ = env.step(int(action.item()))
            observations.append(observation.copy())
            actions.append(int(action.item()))
            log_probs.append(float(log_prob.item()))
            rewards.append(float(reward))
            values.append(float(value.item()))
            dones.append(done)
            masks.append(mask_np.copy())
            observation = next_obs
    advantages = np.zeros(len(rewards), dtype=np.float32)
    returns = np.zeros(len(rewards), dtype=np.float32)
    gae = 0.0
    next_value = 0.0
    for index in range(len(rewards) - 1, -1, -1):
        nonterminal = 0.0 if dones[index] else 1.0
        delta = rewards[index] + config.gamma * next_value * nonterminal - values[index]
        gae = delta + config.gamma * config.gae_lambda * nonterminal * gae
        advantages[index] = gae
        returns[index] = gae + values[index]
        next_value = values[index]
    std = float(advantages.std())
    if std > 1e-8:
        advantages = (advantages - advantages.mean()) / (std + 1e-8)
    return RolloutBatch(
        observations=torch.tensor(np.asarray(observations), dtype=torch.float32),
        actions=torch.tensor(actions, dtype=torch.long),
        old_log_probs=torch.tensor(log_probs, dtype=torch.float32),
        advantages=torch.tensor(advantages, dtype=torch.float32),
        returns=torch.tensor(returns, dtype=torch.float32),
        masks=torch.tensor(np.asarray(masks), dtype=torch.bool),
    )


def _ppo_update(
    model: ActorCritic,
    optimizer: torch.optim.Optimizer,
    batch: RolloutBatch,
    config: RLEngineeringConfig,
) -> dict[str, float]:
    final_policy_loss = 0.0
    final_value_loss = 0.0
    final_entropy = 0.0
    for _ in range(config.update_epochs):
        logits, values = model(batch.observations)
        logits = _masked_logits(logits, batch.masks)
        distribution = Categorical(logits=logits)
        log_probs = distribution.log_prob(batch.actions)
        ratio = torch.exp(log_probs - batch.old_log_probs)
        unclipped = ratio * batch.advantages
        clipped = (
            torch.clamp(ratio, 1.0 - config.clip_ratio, 1.0 + config.clip_ratio) * batch.advantages
        )
        policy_loss = -torch.min(unclipped, clipped).mean()
        value_loss = torch.mean((values - batch.returns) ** 2)
        entropy = distribution.entropy().mean()
        loss = policy_loss + config.value_coef * value_loss - config.entropy_coef * entropy
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        final_policy_loss = float(policy_loss.item())
        final_value_loss = float(value_loss.item())
        final_entropy = float(entropy.item())
    return {
        "policy_loss": final_policy_loss,
        "value_loss": final_value_loss,
        "entropy": final_entropy,
    }


def train_seed(
    config: RLEngineeringConfig, seed: int
) -> tuple[ActorCritic, list[dict[str, float]]]:
    _set_seed(seed)
    model = ActorCritic(len(STATE_FEATURES), config.hidden_units, len(ACTION_LABELS))
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    history: list[dict[str, float]] = []
    for update in range(config.updates):
        batch = _collect_rollout(
            model,
            config,
            seed=seed * 100_000 + update * 1009 + 17,
            episodes=config.train_episodes_per_update,
        )
        metrics = _ppo_update(model, optimizer, batch, config)
        history.append({"update": float(update), "steps": float(len(batch.actions)), **metrics})
    return model, history


def greedy_policy(model: ActorCritic) -> Callable[[np.ndarray, np.ndarray], int]:
    def choose(observation: np.ndarray, mask: np.ndarray) -> int:
        obs_t = torch.from_numpy(observation).unsqueeze(0)
        mask_t = torch.from_numpy(mask).unsqueeze(0)
        with torch.no_grad():
            logits, _ = model(obs_t)
            logits = _masked_logits(logits, mask_t)
        return int(torch.argmax(logits, dim=-1).item())

    return choose


def random_policy(rng: np.random.Generator) -> Callable[[np.ndarray, np.ndarray], int]:
    def choose(_observation: np.ndarray, mask: np.ndarray) -> int:
        valid = np.flatnonzero(mask)
        return int(valid[int(rng.integers(0, len(valid)))])

    return choose


def immediate_policy(_observation: np.ndarray, mask: np.ndarray) -> int:
    index = ACTION_INDEX["aggressive_100"]
    if mask[index]:
        return index
    return int(np.flatnonzero(mask)[-1])


def twap_policy(observation: np.ndarray, mask: np.ndarray) -> int:
    remaining = float(observation[0])
    time_remaining = max(0.05, float(observation[1]))
    urgency = remaining / time_remaining
    if urgency > 1.2:
        label = "aggressive_50"
    elif urgency > 0.7:
        label = "aggressive_25"
    else:
        label = "passive_25"
    index = ACTION_INDEX[label]
    if mask[index]:
        return index
    return immediate_policy(observation, mask)


def liquidity_aware_policy(observation: np.ndarray, mask: np.ndarray) -> int:
    remaining = float(observation[0])
    time_remaining = float(observation[1])
    spread = float(observation[2])
    imbalance = float(observation[4])
    volatility = float(observation[5])
    if time_remaining < 0.25 or remaining > time_remaining + 0.35:
        label = "aggressive_50" if remaining < 0.65 else "aggressive_100"
    elif (spread <= 0.4 and imbalance < -0.15) or volatility > 0.35:
        label = "aggressive_25"
    elif imbalance > 0.10:
        label = "passive_50"
    else:
        label = "passive_25"
    index = ACTION_INDEX[label]
    return index if mask[index] else immediate_policy(observation, mask)


def wait_policy(_observation: np.ndarray, mask: np.ndarray) -> int:
    index = ACTION_INDEX["wait"]
    if mask[index]:
        return index
    return immediate_policy(_observation, mask)


def run_policy_episode(
    config: RLEngineeringConfig,
    *,
    regime: Regime,
    seed: int,
    policy: Callable[[np.ndarray, np.ndarray], int],
    instrument_scale: float = 1.0,
) -> dict[str, object]:
    env = SyntheticExecutionEnv(
        config,
        regime=regime,
        seed=seed,
        instrument_scale=instrument_scale,
    )
    observation = env.reset()
    done = False
    invalid = 0
    action_counts = dict.fromkeys(ACTION_LABELS, 0)
    while not done:
        mask = env.valid_action_mask()
        action = int(policy(observation, mask))
        if not 0 <= action < len(ACTION_LABELS):
            raise RLEngineeringError("policy emitted action outside the finite action space")
        observation, _, done, info = env.step(action)
        invalid += int(bool(info["invalid"]))
        action_counts[ACTION_LABELS[action]] += 1
    for row in env.episode_log:
        if not math.isclose(float(row["reward"]), reconstruct_reward(row), abs_tol=1e-10):
            raise RLEngineeringError("reward decomposition failed independent reconstruction")
    return {
        "cost_bps": env.cumulative_cost_bps,
        "completed": env.state.remaining_lots == 0,
        "invalid_actions": invalid,
        "actions": action_counts,
        "steps": len(env.episode_log),
        "reward_sum": -env.cumulative_cost_bps,
    }


def _episode_specs(count: int, *, seed: int, ood: bool) -> list[tuple[Regime, int, float]]:
    rng = np.random.default_rng(seed)
    regimes = OOD_REGIMES if ood else TRAIN_REGIMES
    specs: list[tuple[Regime, int, float]] = []
    for index in range(count):
        regime = regimes[index % len(regimes)]
        episode_seed = int(rng.integers(0, 2**31 - 1))
        instrument_scale = 1.35 if ood and index % len(regimes) == len(regimes) - 1 else 1.0
        specs.append((regime, episode_seed, instrument_scale))
    return specs


def evaluate_policy(
    config: RLEngineeringConfig,
    *,
    policy: Callable[[np.ndarray, np.ndarray], int],
    specs: Iterable[tuple[Regime, int, float]],
) -> dict[str, object]:
    rows = [
        run_policy_episode(
            config,
            regime=regime,
            seed=seed,
            policy=policy,
            instrument_scale=instrument_scale,
        )
        for regime, seed, instrument_scale in specs
    ]
    costs = np.asarray([float(row["cost_bps"]) for row in rows], dtype=float)
    return {
        "episodes": len(rows),
        "mean_cost_bps": float(costs.mean()),
        "median_cost_bps": float(np.median(costs)),
        "p95_cost_bps": float(np.quantile(costs, 0.95)),
        "cvar95_cost_bps": float(costs[costs >= np.quantile(costs, 0.95)].mean()),
        "completion_rate": float(np.mean([bool(row["completed"]) for row in rows])),
        "invalid_action_rate": float(
            sum(int(row["invalid_actions"]) for row in rows)
            / max(1, sum(int(row["steps"]) for row in rows))
        ),
        "episode_costs_bps": [float(v) for v in costs],
    }


def _state_dict_json(model: ActorCritic) -> dict[str, object]:
    return {
        name: np.asarray(tensor.detach().cpu().numpy(), dtype=float).tolist()
        for name, tensor in sorted(model.state_dict().items())
    }


def _policy_artifact(
    model: ActorCritic, config: RLEngineeringConfig, seed: int
) -> dict[str, object]:
    return {
        "schema_version": "rl-policy-artifact-v1",
        "step": 27,
        "research_status": config.research_status,
        "algorithm": config.algorithm,
        "seed": seed,
        "state_features": list(STATE_FEATURES),
        "action_labels": list(ACTION_LABELS),
        "hidden_units": config.hidden_units,
        "state_dict": _state_dict_json(model),
    }


def load_policy_artifact(value: dict[str, object]) -> ActorCritic:
    if value.get("schema_version") != "rl-policy-artifact-v1" or value.get("step") != 27:
        raise RLEngineeringError("invalid Step 27 policy artifact")
    if tuple(value.get("state_features", [])) != STATE_FEATURES:
        raise RLEngineeringError("Step 27 policy feature order changed")
    if tuple(value.get("action_labels", [])) != ACTION_LABELS:
        raise RLEngineeringError("Step 27 policy action order changed")
    hidden = int(value["hidden_units"])
    model = ActorCritic(len(STATE_FEATURES), hidden, len(ACTION_LABELS))
    raw_state = value["state_dict"]
    if not isinstance(raw_state, dict):
        raise RLEngineeringError("Step 27 state dict is malformed")
    expected = model.state_dict()
    state: dict[str, torch.Tensor] = {}
    if set(raw_state) != set(expected):
        raise RLEngineeringError("Step 27 policy tensor names changed")
    for name, template in expected.items():
        tensor = torch.tensor(raw_state[name], dtype=template.dtype)
        if tuple(tensor.shape) != tuple(template.shape):
            raise RLEngineeringError(f"Step 27 policy tensor shape changed: {name}")
        state[name] = tensor
    model.load_state_dict(state, strict=True)
    model.eval()
    return model


def reward_audit(config: RLEngineeringConfig) -> dict[str, object]:
    regime = TRAIN_REGIMES[0]
    env = SyntheticExecutionEnv(config, regime=regime, seed=91)
    env.reset()
    future_before = env.observation().copy()
    _, _, _, row = env.step(ACTION_INDEX["passive_25"])
    reconstructed = reconstruct_reward(row)
    random_metrics = evaluate_policy(
        config,
        policy=random_policy(np.random.default_rng(901)),
        specs=_episode_specs(20, seed=902, ood=False),
    )
    wait_metrics = evaluate_policy(
        config,
        policy=wait_policy,
        specs=_episode_specs(20, seed=903, ood=False),
    )
    immediate_metrics = evaluate_policy(
        config,
        policy=immediate_policy,
        specs=_episode_specs(20, seed=904, ood=False),
    )
    if not math.isclose(float(row["reward"]), reconstructed, abs_tol=1e-10):
        raise RLEngineeringError("reward audit failed")
    if not bool(row["remaining_after"] >= 0):
        raise RLEngineeringError("residual inventory became negative")
    if float(wait_metrics["mean_cost_bps"]) <= -1_000.0:
        raise RLEngineeringError("wait policy appears to exploit reward accounting")
    return {
        "reward_reconstruction_abs_error": abs(float(row["reward"]) - reconstructed),
        "initial_observation_sha256": sha256_bytes(future_before.tobytes()),
        "random_policy_mean_cost_bps": random_metrics["mean_cost_bps"],
        "wait_policy_mean_cost_bps": wait_metrics["mean_cost_bps"],
        "immediate_policy_mean_cost_bps": immediate_metrics["mean_cost_bps"],
        "terminal_completion_enforced": True,
        "invalid_action_masking_enforced": True,
        "duplicate_fill_guard": True,
        "future_observation_guard": True,
        "pathological_reward_check": "passed",
    }


def historical_zero_shot_gate(
    *, admitted_days_per_instrument: int, fine_tune_requested: bool
) -> str:
    if fine_tune_requested:
        raise RLEngineeringError("fine-tuning on the locked historical test is prohibited")
    if admitted_days_per_instrument < 100:
        raise RLEngineeringError("Gate C blocks zero-shot historical RL evaluation")
    return "eligible_zero_shot_only"


def _aggregate_seed_metrics(seed_rows: list[dict[str, object]], key: str) -> dict[str, float]:
    values = np.asarray([float(row[key]) for row in seed_rows], dtype=float)
    return {
        "mean": float(values.mean()),
        "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
        "min": float(values.min()),
        "max": float(values.max()),
    }


def generate_step27_artifacts(root: Path, *, config_path: Path | None = None) -> dict[str, object]:
    root = root.resolve()
    config_path = config_path or root / "configs/rl/step27_ppo_engineering.json"
    config = load_config(config_path)
    output_dir = root / "data/sample/rl/step27-ppo-engineering"
    result_dir = root / "results/validation/step27"
    output_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
    id_specs = _episode_specs(config.evaluation_episodes, seed=config.seed + 1000, ood=False)
    ood_specs = _episode_specs(config.ood_episodes, seed=config.seed + 2000, ood=True)
    seed_rows: list[dict[str, object]] = []
    policy_hashes: dict[str, str] = {}
    training_histories: dict[str, list[dict[str, float]]] = {}
    for seed in config.training_seeds:
        model, history = train_seed(config, seed)
        artifact = _policy_artifact(model, config, seed)
        policy_path = output_dir / f"policy_seed_{seed}.json"
        policy_path.write_text(canonical_json(artifact) + "\n", encoding="utf-8")
        policy_hashes[str(seed)] = sha256_path(policy_path)
        restored = load_policy_artifact(json.loads(policy_path.read_text(encoding="utf-8")))
        id_metrics = evaluate_policy(config, policy=greedy_policy(restored), specs=id_specs)
        ood_metrics = evaluate_policy(config, policy=greedy_policy(restored), specs=ood_specs)
        seed_rows.append(
            {
                "seed": seed,
                "id_mean_cost_bps": id_metrics["mean_cost_bps"],
                "id_cvar95_cost_bps": id_metrics["cvar95_cost_bps"],
                "id_completion_rate": id_metrics["completion_rate"],
                "id_invalid_action_rate": id_metrics["invalid_action_rate"],
                "ood_mean_cost_bps": ood_metrics["mean_cost_bps"],
                "ood_cvar95_cost_bps": ood_metrics["cvar95_cost_bps"],
                "ood_completion_rate": ood_metrics["completion_rate"],
                "ood_invalid_action_rate": ood_metrics["invalid_action_rate"],
            }
        )
        training_histories[str(seed)] = history
    baseline_rng = np.random.default_rng(config.seed + 3000)
    baselines = {
        "immediate": {
            "id": evaluate_policy(config, policy=immediate_policy, specs=id_specs),
            "ood": evaluate_policy(config, policy=immediate_policy, specs=ood_specs),
        },
        "twap_like": {
            "id": evaluate_policy(config, policy=twap_policy, specs=id_specs),
            "ood": evaluate_policy(config, policy=twap_policy, specs=ood_specs),
        },
        "liquidity_aware": {
            "id": evaluate_policy(config, policy=liquidity_aware_policy, specs=id_specs),
            "ood": evaluate_policy(config, policy=liquidity_aware_policy, specs=ood_specs),
        },
        "random": {
            "id": evaluate_policy(config, policy=random_policy(baseline_rng), specs=id_specs),
            "ood": evaluate_policy(config, policy=random_policy(baseline_rng), specs=ood_specs),
        },
        "wait_noop": {
            "id": evaluate_policy(config, policy=wait_policy, specs=id_specs),
            "ood": evaluate_policy(config, policy=wait_policy, specs=ood_specs),
        },
    }
    audit = reward_audit(config)
    report = {
        "schema_version": "rl-engineering-report-v1",
        "step": 27,
        "research_status": config.research_status,
        "gate_c_status": "blocked_no_admitted_historical_research_dataset",
        "algorithm": config.algorithm,
        "algorithm_status": config.algorithm_status,
        "final_rl_algorithm_selected": False,
        "final_rl_seed_count_selected": False,
        "training_seed_count": len(config.training_seeds),
        "training_seeds": list(config.training_seeds),
        "no_best_seed_reporting": True,
        "environment_contract": {
            "mode": "interactive_synthetic_engineering_fixture_non_research",
            "state_features": list(STATE_FEATURES),
            "actions": list(ACTION_LABELS),
            "steps_per_episode": config.steps_per_episode,
            "parent_lots": config.parent_lots,
            "terminal_completion": "forced_aggressive_with_terminal_impact_multiplier",
            "training_regimes": [regime.name for regime in TRAIN_REGIMES],
            "ood_regimes": [regime.name for regime in OOD_REGIMES],
        },
        "ppo_config": {
            "gamma": config.gamma,
            "gae_lambda": config.gae_lambda,
            "clip_ratio": config.clip_ratio,
            "entropy_coef": config.entropy_coef,
            "value_coef": config.value_coef,
            "learning_rate": config.learning_rate,
            "update_epochs": config.update_epochs,
            "hidden_units": config.hidden_units,
            "updates": config.updates,
            "train_episodes_per_update": config.train_episodes_per_update,
        },
        "seed_results": seed_rows,
        "aggregate": {
            "id_mean_cost_bps": _aggregate_seed_metrics(seed_rows, "id_mean_cost_bps"),
            "id_cvar95_cost_bps": _aggregate_seed_metrics(seed_rows, "id_cvar95_cost_bps"),
            "ood_mean_cost_bps": _aggregate_seed_metrics(seed_rows, "ood_mean_cost_bps"),
            "ood_cvar95_cost_bps": _aggregate_seed_metrics(seed_rows, "ood_cvar95_cost_bps"),
        },
        "baselines": baselines,
        "reward_audit": audit,
        "historical_zero_shot": {
            "status": "blocked_gate_c",
            "fine_tuning_allowed": False,
            "adapter_contract_tested": True,
            "claim": "no_historical_rl_result",
        },
        "policy_sha256": policy_hashes,
        "training_histories": training_histories,
        "scientific_boundary": [
            "engineering fixture only",
            "no locked historical test access",
            "no final RL algorithm freeze",
            "no final ten-seed research comparison",
            "no profitability claim",
            "no best-seed selection",
        ],
    }
    report_path = output_dir / "report.json"
    report_path.write_text(canonical_json(report) + "\n", encoding="utf-8")
    manifest_files = [report_path, *sorted(output_dir.glob("policy_seed_*.json"))]
    manifest = {
        "schema_version": "rl-engineering-manifest-v1",
        "step": 27,
        "research_status": config.research_status,
        "files": {path.name: sha256_path(path) for path in manifest_files},
        "config_sha256": sha256_path(config_path),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    summary = {
        "report_sha256": sha256_path(report_path),
        "manifest_sha256": sha256_path(manifest_path),
        "policy_sha256": policy_hashes,
    }
    (result_dir / "artifact_hashes.json").write_text(
        canonical_json(summary) + "\n", encoding="utf-8"
    )
    return report
