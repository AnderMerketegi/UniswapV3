from wallet.wallet import Wallet


def main():

    my_wallet = Wallet()

    address = my_wallet.address
    print(f"Wallet address: {address}")

    balance = my_wallet.get_balance()
    print(f"Wallet balance: {balance}")


if __name__ == "__main__":
    main()
