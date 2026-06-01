import pytest
import pandas as pd


@pytest.fixture
def sample_weather_row():
    return {
        "Location": "Sydney",
        "MinTemp": 13.4,
        "MaxTemp": 22.9,
        "Rainfall": 0.6,
        "Evaporation": 4.8,
        "Sunshine": 7.0,
        "WindGustDir": "W",
        "WindGustSpeed": 44.0,
        "WindDir9am": "W",
        "WindDir3pm": "WNW",
        "WindSpeed9am": 20.0,
        "WindSpeed3pm": 24.0,
        "Humidity9am": 71.0,
        "Humidity3pm": 22.0,
        "Pressure9am": 1007.7,
        "Pressure3pm": 1007.1,
        "Cloud9am": 8.0,
        "Cloud3pm": 5.0,
        "Temp9am": 16.9,
        "Temp3pm": 21.8,
        "RainToday": 0,
        "Month": 1,
        "Day": 1,
    }


@pytest.fixture
def sample_weather_df(sample_weather_row):
    return pd.DataFrame([sample_weather_row] * 5)
