from typing import Dict, List, Tuple

import pandas as pd
import plotly.subplots as sp
import plotly.graph_objects as go
from pandera.typing import DataFrame
from StratDaemon.models.crypto import CryptoHistorical, CryptoOrder


def find_loc(df, dates):
    marks = []
    for date in dates:
        marks.append(df.index[df.timestamp == date])
    return marks


class GraphHandler:
    @staticmethod
    def graph_positions(
        dict_of_dfs: Dict[str, DataFrame[CryptoHistorical]],
        transactions: List[CryptoOrder],
        show_enter_exit: bool = True,
    ):
        for currency_code, df in dict_of_dfs.items():
            df.set_index("timestamp", inplace=True, drop=False)
            req_df_cols = ["rsi"]
            n = 1 + len(req_df_cols)

            fig = sp.make_subplots(
                rows=1 + len(req_df_cols),
                cols=1,
                shared_xaxes="rows",
                subplot_titles=[
                    f"{currency_code} Crypto Price",
                    "Technical Indicators",
                ],
                vertical_spacing=0.5,
                row_heights=[0.7, 0.3],
            )

            fig.add_trace(
                go.Candlestick(
                    x=df.index,
                    open=df["open"],
                    high=df["high"],
                    low=df["low"],
                    close=df["close"],
                    name="Crypto Price",
                ),
                row=1,
                col=1,
            )

            for pos in transactions:
                list_dates = [pos.timestamp]
                list_locs = find_loc(df, list_dates)

                if show_enter_exit:
                    GraphHandler.add_graph_annotations(
                        fig,
                        df.loc[list_locs[0]],
                        pos,
                        "Enter" if pos.side == 1 else "Exit",
                        df.index[0],
                    )

            # Upper Bound
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["upper_bb"],
                    line_color="gray",
                    line={"dash": "dash"},
                    name="upper band",
                    opacity=0.01,
                ),
                row=1,
                col=1,
            )

            # Lower Bound fill in between with parameter 'fill': 'tonexty'
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["lower_bb"],
                    line_color="gray",
                    line={"dash": "dash"},
                    fill="tonexty",
                    name="lower band",
                    opacity=0.01,
                ),
                row=1,
                col=1,
            )

            colors = ["blue", "purple", "orange"]

            for i, col in enumerate(req_df_cols):
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df[col],
                        mode="lines",
                        line=dict(color=colors[i % len(colors)]),
                        name=col,
                        xaxis="x2",
                    ),
                    row=2 + i,
                    col=1,
                )

            # order_type = "Buy" if position.order_type == 1 else "Sell"

            fig.update_layout(
                xaxis_rangeslider_visible=False,
                template="plotly_white",
                title_text=f"{currency_code} Crypto Analysis",
                xaxis_title_text="Date",
                yaxis_title_text="Price",
                yaxis2_title_text=req_df_cols[0],
                height=800,  # Set the height of the figure
                width=1200,
            )  # Set the width of the figure

            fig.write_html(f"results/{currency_code}_analysis.html")
            fig.write_image(f"results/{currency_code}_analysis.png")
            fig.show()

    @staticmethod
    def add_graph_annotations(
        input_fig, list_locs, position: CryptoOrder, post_type, start_index=0
    ):
        input_fig.add_annotation(
            x=list_locs["timestamp"].index[0],
            y=list_locs["close"].iloc[0],
            text=f"<b>{position.side.upper()}<b>",
            showarrow=True,
            arrowhead=1,
            font=dict(size=14, color="green" if position.side == "buy" else "red"),
        )
