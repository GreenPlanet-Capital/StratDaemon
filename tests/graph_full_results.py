import pandas as pd
import plotly.express as px

df = pd.read_csv("results/performance_full.csv")

fig = px.line(df, x='date_start', y="portfolio_value")
fig.write_image("results/performance_full.png")