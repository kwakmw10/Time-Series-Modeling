# -*- coding: utf-8 -*-
"""datasci 415 FINAL PROJECT (new)

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1OR1NTfhVk0C89iRp0eGHyitD5OogO97x
"""

!pip install ta

import yfinance as yf
import pandas as pd
import ta
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.stattools import adfuller
from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.svm import SVR
from sklearn.model_selection import TimeSeriesSplit
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
import matplotlib.dates as mdates
import matplotlib as mpl
mpl.rcParams['figure.figsize'] = (10, 4)

import warnings

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# nvidia data

nvidia = yf.download('NVDA', start = '2023-01-01', end = '2023-12-31',
                     interval = "1d").dropna()
nvidia.index = pd.to_datetime(nvidia.index)

close, high = nvidia["Close"].squeeze(), nvidia["High"].squeeze()
low, volume = nvidia["Low"].squeeze(), nvidia["Volume"].squeeze()

nvidia["OBV"] = ta.volume.OnBalanceVolumeIndicator(close = close,
                                                   volume = volume).on_balance_volume()

nvidia["AD"] = ta.volume.AccDistIndexIndicator(high = high, low = low,
                                               close = close,
                                               volume = volume).acc_dist_index()

nvidia["ADX"] = ta.trend.ADXIndicator(high=high, low = low,
                                      close = close, window = 14).adx()

macd = ta.trend.MACD(close)
nvidia["MACD"], nvidia["MACD Signal"] = macd.macd(), macd.macd_signal()
nvidia["MACD Diff"] = macd.macd_diff()

nvidia["RSI"] = ta.momentum.RSIIndicator(close, window=14).rsi()

stoch = ta.momentum.StochasticOscillator(high, low, close,
                                         window=14, smooth_window=3)
nvidia["Stoch"], nvidia["Stoch Signal"] = stoch.stoch(), stoch.stoch_signal()

nvidia = nvidia.replace([np.inf, -np.inf], np.nan).dropna()

# adding 'google search trend' to the nvidia dataset

search = pd.read_csv('search.csv', skiprows = 2)
search['Week'] = pd.to_datetime(search['Week'])

start_date = search['Week'].min()
end_date = search['Week'].max()
all_dates = pd.date_range(start=start_date, end = end_date, freq = 'D')

search_all = pd.DataFrame({'Week': all_dates})
search_all = pd.merge(search_all, search, on = 'Week', how = 'left')
search_all.fillna(method = 'ffill', inplace = True)

nvidia_reset = nvidia.reset_index()
nvidia_reset.columns = ['_'.join(col).strip() for col in nvidia_reset.columns]

nvidia_new = pd.merge(search_all, nvidia_reset, left_on = 'Week',
                      right_on = 'Date_', how = 'left').dropna(subset = ['Date_'])

nvidia_new.drop(columns = ['Week'], inplace = True)
nvidia_new.rename(columns = {'nvidia: (United States)': 'Search'},
                  inplace = True)
nvidia_new.columns = [col.split('_')[0] for col in nvidia_new.columns]
nvidia_new.index = pd.to_datetime(nvidia.index)

# universal variables to use later

close_prices = nvidia_new['Close']
training_size = int(len(close_prices) * 0.8)

small_var = nvidia_new[['Open', 'High', 'Low', 'Volume']]
cross_small_var = small_var.loc[close_prices.index]

big_var = nvidia_new[['Open', 'High', 'Low', 'Volume', 'OBV', 'AD', 'ADX', 'MACD',
                  'MACD Signal', 'MACD Diff', 'RSI', 'Stoch', 'Stoch Signal',
                  'Search']]
cross_big_var = big_var.loc[close_prices.index]

nvidia_new.tail()

"""SMA model (Baseline)"""

# SMA model (Baseline)

nvidia_new['SMA'] = nvidia_new['Close'].rolling(window = 5).mean()

# plot a graph for SMA against actual closing prices

plt.plot(nvidia_new.index, nvidia_new['Close'], label = 'Actual')
plt.plot(nvidia_new.index, nvidia_new['SMA'], label = 'Forecast', color = 'red')
plt.xlabel('Date')
plt.ylabel('Price')
plt.title('SMA model (baseline)')
plt.legend()
plt.show()

"""cross val with sma"""

# cross validation for SMA

sma_mse, sma_mae = [], []

for i, j in TimeSeriesSplit(n_splits = 10).split(nvidia_new):
    train, test = nvidia.iloc[i], nvidia.iloc[j]
    train_sma = train['Close'].rolling(window=5).mean().dropna()

    predictions = train_sma[-len(test):]
    test_sma = test.iloc[-len(predictions):]

    sma_mse.append(mean_squared_error(test_sma['Close'], predictions))
    sma_mae.append(mean_absolute_error(test_sma['Close'], predictions))

print("Mean Absolute Error:", np.mean(sma_mae))
print("Mean Squared Error:", np.mean(sma_mse))

"""ARIMA with Historical data"""

# ARIMA(1) model (only historical data)

train, test = close_prices[:training_size], close_prices[training_size:]
train_arima, test_arima = small_var.iloc[:training_size], small_var.iloc[training_size:]

model_arima = (ARIMA(train, order=(5, 1, 0), exog = train_arima)).fit()
forecast = model_arima.forecast(steps = len(test), exog = test_arima)

# plot a graph for ARIMA(1) against actual closing prices

plt.plot(train, label = 'Training Data')
plt.plot(test.index, test, label = 'Actual', color = 'blue')
plt.plot(test.index, forecast, label = 'Forecast', color = 'red')
plt.xlabel('Date')
plt.ylabel('Price')
plt.title('ARIMA Model with Historical Data')
plt.legend()
plt.show()

"""Cross Validation testing for ARIMA with historical data"""

# cross validation for ARIMA(1)

arima_mae, arima_mse = [], []

for i, j in TimeSeriesSplit(n_splits = 10).split(close_prices):
    train, test = close_prices.iloc[i], close_prices.iloc[j]
    train_arima, test_arima = cross_small_var.iloc[i], cross_small_var.iloc[j]

    model_arima = (ARIMA(train, order = (5, 1, 0), exog = train_arima)).fit()
    forecast = model_arima.forecast(steps = len(test), exog = test_arima)

    arima_mae.append(mean_absolute_error(test, forecast))
    arima_mse.append(mean_squared_error(test, forecast))

print("Mean Absolute Error:", np.mean(arima_mae))
print("Mean Squared Error:", np.mean(arima_mse))

"""ARIMA with Historical data and market sentiment"""

# ARIMA(2) model (historical and market sentiment data)

train, test = close_prices[:training_size], close_prices[training_size:]
train_arimahm, test_arimahm = big_var.iloc[:training_size], big_var.iloc[training_size:]

model_arimahm = (ARIMA(train, order=(5, 1, 0), exog = train_arimahm)).fit()
forecast = model_arimahm.forecast(steps=len(test), exog = test_arimahm)

# plot a graph for ARIMA(2) against actual closing prices

plt.plot(train, label = 'Training Data')
plt.plot(test.index, test, label = 'Actual', color = 'blue')
plt.plot(test.index, forecast, label = 'Forecast', color = 'red')
plt.xlabel('Date')
plt.ylabel('Price')
plt.title('ARIMA Model with Historical and Market Sentiment Data')
plt.legend()
plt.show()

"""Cross Val testing for ARIMA WITH market sentiment"""

# cross validation for ARIMA(2)

arimahm_mae, arimahm_mse = [], []

for i, j in TimeSeriesSplit(n_splits = 10).split(close_prices):
    train, test = close_prices.iloc[i], close_prices.iloc[j]

    train_arimahm, test_arimahm = cross_big_var.iloc[i], cross_big_var.iloc[j]

    model_arimahm = (ARIMA(train, order = (5, 1, 0), exog = train_arimahm)).fit()
    forecast = model_arimahm.forecast(steps = len(test), exog = test_arimahm)

    arimahm_mae.append(mean_absolute_error(test, forecast))
    arimahm_mse.append(mean_squared_error(test, forecast))

print("Mean Absolute Error:", np.mean(arimahm_mae))
print("Mean Squared Error:", np.mean(arimahm_mse))

"""SVM with Historical data"""

# SVM(1) model (only historical data)

train, test = close_prices[:training_size], close_prices[training_size:]
train_svm, test_svm = small_var.iloc[:training_size], small_var.iloc[training_size:]

model_svm = SVR(kernel='rbf').fit(train_svm, train)
forecast = model_svm.predict(test_svm)

# plot a graph for SVM(1) against actual closing prices

plt.plot(train.index, train, label = 'Training Data')
plt.plot(test.index, test, label = 'Actual', color = 'blue')
plt.plot(test.index, forecast, label = 'Forecast', color = 'red')
plt.xlabel('Date')
plt.ylabel('Price')
plt.title('SVM Model with Historical Data')
plt.legend()
plt.show()

"""Cross Val testing for SVM with Historical Data"""

# cross validation for SVM(1)

svm_mae, svm_mse = [], []

for i, j in TimeSeriesSplit(n_splits = 10).split(close_prices):
    train, test = close_prices.iloc[i], close_prices.iloc[j]
    train_svm, test_svm = cross_small_var.iloc[i], cross_small_var.iloc[j]

    model_svm = SVR(kernel='rbf').fit(train_svm, train)
    forecast = model_svm.predict(test_svm)

    svm_mae.append(mean_absolute_error(test, forecast))
    svm_mse.append(mean_squared_error(test, forecast))

print("Mean Absolute Error:", np.mean(svm_mae))
print("Mean Squared Error:", np.mean(svm_mse))

"""SVM with Historical data and market sentiment"""

# SVM(2) model (only historical data)

train, test = close_prices[:training_size], close_prices[training_size:]
train_svmhm, test_svmhm = big_var.iloc[:training_size], big_var.iloc[training_size:]

model_svm = SVR(kernel='rbf').fit(train_svmhm, train)
forecast = model_svm.predict(test_svmhm)

# plot a graph for SVM(2) against actual closing prices

plt.plot(train.index, train, label = 'Training Data')
plt.plot(test.index, test, label = 'Actual', color = 'blue')
plt.plot(test.index, forecast, label = 'Forecast', color = 'red')
plt.xlabel('Date')
plt.ylabel('Price')
plt.title('SVM Model with Historical and Market Sentiment Data')
plt.legend()
plt.show()

"""Cross Val testing for ARIMA WITH market sentiment"""

# cross validation for SVM(2)

svmhm_mae, svmhm_mse = [], []

for i, j in TimeSeriesSplit(n_splits = 10).split(close_prices):
    train, test = close_prices.iloc[i], close_prices.iloc[j]
    train_svmhm, test_svmhm = cross_big_var.iloc[i], cross_big_var.iloc[j]

    model_svm = SVR(kernel='rbf').fit(train_svmhm, train)
    forecast = model_svm.predict(test_svmhm)

    svmhm_mae.append(mean_absolute_error(test, forecast))
    svmhm_mse.append(mean_squared_error(test, forecast))

print("Mean Absolute Error:", np.mean(svmhm_mae))
print("Mean Squared Error:", np.mean(svmhm_mse))

"""2024 december prediction"""

# re-download nvidia for fresh dataset

nvidia = yf.download('NVDA', start = '2023-01-01', end = '2024-11-30',
                     interval = "1d").dropna()
nvidia.index = pd.to_datetime(nvidia.index).strftime('%Y-%m-%d')
nvidia = nvidia.replace([np.inf, -np.inf], np.nan).dropna()

close, high = nvidia["Close"].squeeze(), nvidia["High"].squeeze()
low, volume = nvidia["Low"].squeeze(), nvidia["Volume"].squeeze()

train = nvidia['Close']
var = nvidia[['Open', 'High', 'Low', 'Volume']]

# using ARIMA(1) model - which came out to be the best model with lowest MAE, MSE

model = ARIMA(train, order = (5, 1, 0), exog = var).fit()

# predicting 20 days

predicting_dates = 20
last_values = var.iloc[-1].values
future_exog = np.tile(last_values, (predicting_dates, 1))

forecast = model.forecast(steps = predicting_dates, exog = future_exog)
prediction = pd.date_range(start = pd.to_datetime(train.index[-1]),
                               periods = predicting_dates + 1, freq = 'B')[1:]


# plot a graph for Dec 2024 (prediction)

plt.plot(pd.to_datetime(train.index), train, label = 'Training Data')
plt.plot(prediction, forecast, label = 'Forecasted Prices', color = 'blue')
plt.xlabel('Date')
plt.ylabel('Price')
plt.title('ARIMA Model with Historical Variables Forecasting')
plt.legend()
plt.show()

# make a table of prediction

print(pd.DataFrame({'Date': prediction, 'Forecasting': forecast}))