import pandas as pd

MAX_NUM_TRADES = 50

df = pd.read_csv("results/performance.csv")
df = df.sort_values("final_value", ascending=False)

df["num_trades"] = df["num_buy_trades"] + df["num_sell_trades"]
df = df[(df["num_trades"] > 0) & (df["num_trades"] < MAX_NUM_TRADES)]

print(df)
