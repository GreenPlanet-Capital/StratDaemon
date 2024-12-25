import pandas as pd
import plotly.express as px

df = pd.read_csv("results/performance_full.csv")
# keep last among duplicates
df = df.drop_duplicates(subset='date_start', keep='last')

fig = px.line(df, x='date_start', y="portfolio_value")
fig.write_image("results/performance_full.png")