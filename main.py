from logs.logger import Logger
from wallet.wallet import Wallet
from uniswapV3.uniswapV3 import UniswapV3


def main():

    logger = Logger()

    my_wallet = Wallet()

    address = my_wallet.address
    logger.info(f"Wallet address: {address}")

    balance = my_wallet.get_balance()
    logger.info(f"Wallet balance: {balance}")

    # Get UniswapV3 active pools
    uniswap_v3 = UniswapV3(my_wallet.web3, my_wallet.address)
    uniswap_v3.get_active_pools()


if __name__ == "__main__":
    main()
