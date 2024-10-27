import pandas as pd


def get_normalized_value(x, lower_bound, upper_bound, max_x, min_x):
    return (
        ((upper_bound - lower_bound) * (x - min_x))
        / ((max_x - min_x) if max_x != min_x else 1e-6)
    ) + lower_bound


def normalize_values(series: pd.Series, lower_bound, upper_bound) -> pd.Series:
    min_x = series.min()
    max_x = series.max()

    args = (lower_bound, upper_bound, max_x, min_x)
    series_out = series.apply(get_normalized_value, args=args)
    return series_out
