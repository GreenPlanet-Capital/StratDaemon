import pandas as pd
import sys

MAX_NUM_TRADES = 1e10

ASC = True if len(sys.argv) > 1 and sys.argv[1] == "asc" else False


def column_rename(x):
    x_parts = x.split("_")
    if len(x_parts) > 1:
        return x_parts[0][0] + "_" + x_parts[1]
    return x


df = pd.read_csv("results/performance.csv")
df = df.sort_values("final_value", ascending=ASC)

df["num_trades"] = df["num_buy_trades"] + df["num_sell_trades"]
df = df[(df["num_trades"] >= 0) & (df["num_trades"] < MAX_NUM_TRADES)]
df.rename(columns=column_rename, inplace=True)
df.drop_duplicates(inplace=True)

print(df.head(10))
