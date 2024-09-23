from logs.logger import Logger
from wallet.wallet import Wallet


def main():

    logger = Logger()

    my_wallet = Wallet()

    address = my_wallet.address
    logger.info(f"Wallet address: {address}")

    balance = my_wallet.get_balance()
    logger.info(f"Wallet balance: {balance}")


if __name__ == "__main__":
    main()
