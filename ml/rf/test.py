import pandas as pd
import gymnasium as gym
import gym_trading_env
from more_itertools import numeric_range

from StratDaemon.integration.broker.crypto_compare import CryptoCompareBroker
from StratDaemon.strats.fib_vol_rsi import FibVolRsiStrategy

EPISODES = 1
CURRENCY_CODE = "DOGE"

broker = CryptoCompareBroker()

strat = FibVolRsiStrategy(
    broker, None, None, [CURRENCY_CODE], auto_generate_orders=True
)

df = broker.get_crypto_historical("DOGE", "hour", pull_from_api=False)
df = strat.transform_df(df)
df.set_index("timestamp", inplace=True)
df.sort_index(inplace=True)
df.dropna(inplace=True)
df.drop_duplicates(inplace=True)

# The environment will recognize as inputs every column that contains the keyword 'feature' in its name.
df["feature_close"] = df["close"].pct_change()

cols_to_make_features = ["boll_diff", "rsi", "trends_upwards"]
for col in cols_to_make_features:
    df[f"feature_{col}"] = df[col]

print("Using features: ", [col for col in df.columns if "feature" in col])
df.dropna(inplace=True)

env = gym.make(
    "TradingEnv",
    name="DOGEUSD",
    df=df,  # Your dataset with your custom features
    positions=list(numeric_range(0, 1.1, 0.1)),  # -1 (=SHORT), 0(=OUT), +1 (=LONG)
    trading_fees=0.01 / 100,  # 0.01% per stock buy / sell (Binance fees)
    borrow_interest_rate=0.0003 / 100,  # 0.0003% per timestep (one timestep = 1h here)
    portfolio_initial_value=1000,
)


# Run 100 episodes
for _ in range(EPISODES):
    # At every episode, the env will pick a new dataset.
    done, truncated = False, False
    observation, info = env.reset()
    while not done and not truncated:
        position_index = env.action_space.sample()  # Pick random position index
        observation, reward, done, truncated, info = env.step(position_index)

env.unwrapped.save_for_render(dir="./render_logs")
