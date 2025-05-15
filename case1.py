import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.accounts as accounts
import google.generativeai as genai

import re
import time
import json
import os

from dotenv import load_dotenv
from oandapyV20 import API

load_dotenv()  # Load environment variables from .env file

account_id = os.environ.get("OANDA_ACCOUNT_ID")
oanda_api_key = os.environ.get("OANDA_API_KEY")
oanda_environment = os.environ.get("OANDA_ENVIRONMENT")

if not account_id:
    raise EnvironmentError("OANDA_ACCOUNT_ID environment variable not set.")
if not oanda_api_key:
    raise EnvironmentError("OANDA_API_KEY environment variable not set.")

# Initialize the OANDA API client
oanda = API(access_token=oanda_api_key, environment=oanda_environment)

print(f"Successfully connected to OANDA ({oanda_environment} environment).")

# Example of fetching account details (now passing account_id)
r = accounts.AccountDetails(accountID=account_id)
oanda.request(r)
if r.status_code == 200:
    account_bal = r.response['account']['balance']
    print(f"Account balance: {account_bal}")
else:
    print(f"Error fetching account details: {r.status_code} - {r.response}")
    print(f"Response: {r.response}")

def place_order(instrument, units, order_type, price=None, stop_loss_price=None, take_profit_price=None):
    """
    Places an order of a specified type and prints the API response.

    Args:
        instrument (str): The instrument to trade (e.g., "EUR_USD").
        units (int): The number of units to trade (positive for buy, negative for sell).
        order_type (str): The type of order ("MARKET", "LIMIT", "STOP").
        price (float, optional): The price for LIMIT or STOP orders. Defaults to None.
        stop_loss_price (float, optional): The stop loss price. Defaults to None.
        take_profit_price (float, optional): The take profit price. Defaults to None.

    Returns:
        bool: True if the order is placed successfully, False otherwise.  Prints order details or error.
    """
    order_data = {
        "order": {
            "instrument": instrument,
            "units": str(units),
            "type": order_type,
            "positionFill": "DEFAULT",  # Or "REDUCE_ONLY", "REDUCE_FIRST", etc.
        }
    }

    if price is not None:
        order_data["order"]["price"] = str(price)

    if stop_loss_price:
        order_data["order"]["stopLossOnFill"] = {
            "timeInForce": "GTC",
            "price": str(stop_loss_price)
        }

    if take_profit_price:
        order_data["order"]["takeProfitOnFill"] = {
            "timeInForce": "GTC",
            "price": str(take_profit_price)
        }

    r = orders.OrderCreate(accountID=account_id, data=order_data)
    oanda.request(r)

    if r.status_code == 201:
        print(f"{order_type} order placed successfully:\n{r.response}")
        return True
    else:
        print(f"Error placing {order_type} order:\nStatus Code: {r.status_code}\nResponse: {r.response}")
        return False

######################################################################################
google_api_key = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=google_api_key) # Or try 'v1' if available
model = genai.GenerativeModel('gemini-2.0-flash')

#########################################################################################
prompt1 = f"""
You are a simulated forex trading assistant operating in a demo environment. Once per week, you generate one swing trade idea based on current market conditions.

Account size: ${account_bal}  
Risk per trade: 1 percent of ${account_bal}  
Pip value: ~$1 per 10,000 units

Return the output in this format:
<str, The instrument to trade (e.g., "EUR_USD")>

Do not include any extra text.
"""
response1 = model.generate_content(prompt1)

def get_current_price(instrument):
    params = {"instruments": instrument}
    r = pricing.PricingInfo(accountID=account_id, params=params)
    oanda.request(r)
    prices = r.response['prices'][0]
    bid = float(prices['bids'][0]['price'])
    ask = float(prices['asks'][0]['price'])
    return (bid + ask) / 2  # Mid price

simulated_instrument = response1.candidates[0].content.parts[0].text.strip()
market_price = get_current_price(simulated_instrument)
market_price_str = f"{market_price:.5f}"
print(f"The current market price of {simulated_instrument} is {market_price_str}")

#########################################################################################
trade_risk = float(account_bal)/100
trade_risk = str(trade_risk)
print(f"The trade risk is {trade_risk}")

prompt2 =  f"""
You are a forex trading assistant in a demo environment. Each week, generate **one swing trade** idea based on the provided forex pair and current price.
price, stop_loss_price and take_profit_price are to be rounded to 3 decimal places.
Only return the trade idea in the following **exact format** (no commentary, no extra text):

Args:
instrument: "{simulated_instrument}"
units: <int>
order_type: "<MARKET or STOP or LIMIT>"
price: <float or None>
stop_loss_price: <float>
take_profit_price: <float>
reason: "<string explaining the trade idea in roughly two sentences>"

Your trade should risk ${trade_risk} SGD. Calculate position size using stop loss distance assuming $1 per 1000 units. Round units to the nearest 100.

Current price for {simulated_instrument} is {market_price}.
"""
response2 = model.generate_content(prompt2)

# Match: key: "value" or key: value (including None)
pattern = r'^\s*(\w+):\s+"?([^"\n]+)"?$'

trade_args = {}

for line in response2.text.splitlines():
    match = re.match(pattern, line)
    if match:
        key, value = match.groups()

        # Convert value properly
        if value == "None":
            trade_args[key] = None
        elif key == "units":
            trade_args[key] = int(value)
        elif key in ["price", "stop_loss_price", "take_profit_price"]:
            trade_args[key] = float(value)
        else:
            trade_args[key] = value

# Assign variables
response_instrument = trade_args.get("instrument")
response_units = trade_args.get("units")
response_order_type = trade_args.get("order_type")
response_price = trade_args.get("price")
response_stop_loss_price = trade_args.get("stop_loss_price")
response_take_profit_price = trade_args.get("take_profit_price")
response_reason = trade_args.get("reason")

# Print to verify
print("Parsed trade args:")
print(f"Instrument: {response_instrument}")
print(f"Units: {response_units}")
print(f"Order Type: {response_order_type}")
print(f"Price: {response_price}")
print(f"Stop Loss: {response_stop_loss_price}")
print(f"Take Profit: {response_take_profit_price}")
print(f"Reason: {response_reason}")

#########################################################################################
if __name__ == "__main__":

    # Place an order
    print("Placing the order:")
    order_successful = place_order(
        instrument=response_instrument,
        units=response_units,
        order_type=response_order_type,
        price=response_price,
        stop_loss_price=response_stop_loss_price,
        take_profit_price=response_take_profit_price
    )
    if order_successful:
        print("Order was successful")
    else:
        print("Order failed")