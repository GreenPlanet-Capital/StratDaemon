import pandas as pd

MAX_NUM_TRADES = 70


def column_rename(x):
    x_parts = x.split("_")
    if len(x_parts) > 1:
        return x_parts[0][0] + "_" + x_parts[1]
    return x


df = pd.read_csv("results/performance.csv")
df = df.sort_values("final_value", ascending=False)

df["num_trades"] = df["num_buy_trades"] + df["num_sell_trades"]
df = df[(df["num_trades"] > 0) & (df["num_trades"] < MAX_NUM_TRADES)]
df.rename(columns=column_rename, inplace=True)


print(df.head(10))
