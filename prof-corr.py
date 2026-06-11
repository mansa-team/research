import pandas as pd
import numpy as np

from sklearn.preprocessing import StandardScaler

stock1 = np.array([])
stock2 = np.array([])

"""
to be used to compose the views of the black-litterman together with the xango investing scores

the main idea is to analyze the compostition from the profits of a stock over a 10 year period and compare stocks i,j to get a corr between their growths

x = year
y = profit

the profits would be scaled to be measured in a similar space
profits that grow together might indicate a market relation, in which the model would adapt the weight allocation based on that corr score

the evaluation of the difference from the growth of profits from t and t-1 or the direct comparasion between the y1 and y2, meaning that a MSE loss function would be used to evaluate a loss for the corr, the only problem is that, i fear that the scaler might not be able to adapt this properly or it would be able to catch the corr between stocks. or that a loss that is bigger between 2 points mean that the profit from the stock i might have been lower, not necessarily indicating a correlation

in a good makret, where stokcs grow their profits over and over, a profit correlation might be overfit, because the market will just be in a good phase, prioritizing stocks with less growth between each other, ruining the portfolios performance according to the mansas strategy


initial plan:

sum(mse) * -1 (inversion, lower loss better)
sigmoid or tahn * 0.5 (prob tahn because its derivative is higher than sigmoid's)
this would allow for a moldable corr model because of the k value in sigmoid and tahn to shift the threshold.

would compute the corr between all stocks i,j except when the ticker(i) == ticker(j)

so i can have

i - j
j - i

because the corr of them would be different, because mse is calculated with (y1 - y2)^2


scale the value to 100 base


possible problems:
- the corr might not show nothing because of the standardscaler, might just measure how big is the gap between one company and another in profits
- doesnt account for a healthy market


plan 2:
instead of measuring the profit values directly, measure the difference in growth between them in a t-1 and t time periods, convert it to % and use this as input data for y instead, comparing to the profit growth from another stock in the same period.

the rest stays the same, the only thing that changes is that

possible problems:
- doesnt account for a healthy market

possible solutions for the healthy market approach:
- consider, inside the picked of stocks through their score (> 60) the average growth in t-1 and t so it can evaluate a threshold for the mse. this would prob require a new loss function of to measure the diffrences between the percentages in growth from t-1 and t or some other equational approach
"""