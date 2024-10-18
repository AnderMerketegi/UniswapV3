import json
import math
import toml
import requests

from logs.logger import Logger

logger = Logger()


def load_config():
    return toml.load("blockchain/blockchain.toml")


def load_position():
    return toml.load("uniswapV3/position.toml")


def load_abi(path: str):
    """
    Loads the ABI from a given file path.
    :param path: Path to the ABI JSON file.
    :return: ABI loaded from the file.
    """
    with open(path, 'r') as abi_file:
        return json.load(abi_file)


def price_to_tick(price, decimal_token0, decimal_token1):
    """
    Converts a price to a tick value, adjusted for the token decimals in Uniswap V3.

    :param price: The price to convert to tick.
    :param decimal_token0: The number of decimals for token0.
    :param decimal_token1: The number of decimals for token1.
    :return: The tick value corresponding to the adjusted price.
    """
    # Adjust the price based on the difference in token decimals
    price_adjusted = price * (10 ** (decimal_token1 - decimal_token0))

    # Calculate the tick by taking the log base 1.0001 and rounding it to the nearest integer
    tick = int(math.log(price_adjusted, 1.0001))

    return tick


def calculate_ticks(price_current, price_range, decimals_token0, decimals_token1, fee):
    """
    Calculates the tick ranges based on the price range and token decimals.
    """
    price_lower = price_current * price_range[0]
    price_upper = price_current * price_range[1]

    tick_lower = price_to_tick(price_lower, decimals_token0, decimals_token1)
    tick_upper = price_to_tick(price_upper, decimals_token0, decimals_token1)

    fee_tier_tick_spacing = {100: 1, 500: 10, 3000: 60, 10000: 200}
    tick_spacing = fee_tier_tick_spacing[fee]

    # Adjust ticks according to the tick spacing
    tick_lower = (tick_lower // tick_spacing) * tick_spacing
    tick_upper = (tick_upper // tick_spacing) * tick_spacing

    return tick_lower, tick_upper


def token_to_usd(network: str, token_address: str):
    """
    Retrieves the price of a token in USD using the CoinGecko API.

    :param network: The blockchain corresponding to the token address.
    :param token_address: The contract address of the token.
    :return: The price of the token in USD.
    """

    available_networks = get_available_networks()
    if network not in available_networks:
        logger.error(f"Network unavailavle: {network}")

    # CoinGecko API endpoint for Ethereum token prices
    coingecko_api_url = load_config()["networks"][network]["coingecko_url"]

    # Convert token address to lowercase to match CoinGecko format
    token_address = token_address.lower()

    # Parameters for the API call
    params = {
        'contract_addresses': token_address,
        'vs_currencies': 'usd'
    }

    try:
        # Make the API call to get the token price
        response = requests.get(coingecko_api_url, params=params)
        data = response.json()

        # Check if the token is in the response data
        if token_address in data:
            return data[token_address]['usd']
        else:
            logger.error(f"Token address {token_address} not found in CoinGecko data.")
            return None

    except Exception as e:
        logger.error(f"Error fetching token price for {token_address}: {e}")
        return None


def get_available_networks():
    """
    Returns a list of available network names from the configuration file.

    :return: List of network names.
    """
    return list(load_config()['networks'].keys())



