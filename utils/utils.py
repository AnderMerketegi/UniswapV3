import toml


def load_config():
    return toml.load("../blockchain/blockchain.toml")

