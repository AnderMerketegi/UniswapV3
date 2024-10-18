from logs.logger import Logger
from wallet.wallet import Wallet
from uniswapV3.uniswapV3 import UniswapV3

from utils.utils import load_config, load_position


def main():

    logger = Logger()

    my_wallet = Wallet()

    address = my_wallet.address
    logger.info(f"Wallet address: {address}")

    balance = my_wallet.get_balance()
    logger.info(f"Wallet balance: {balance}")

    # Add liquidity to WETH/USDT pool equivalent to 10 USD por each token
    uniswap_v3 = UniswapV3(my_wallet.network, my_wallet.web3, my_wallet.address)
    uniswap_v3.add_liquidity(amount_usdt=10, price_range=(0.95, 1.05))


if __name__ == "__main__":
    main()
