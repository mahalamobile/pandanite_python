from pandanite.core.common import TransactionAmount
from pandanite.core.helpers import PDN
from pandanite.core.transaction import Transaction
from pandanite.core.crypto import (
    PublicWalletAddress,
    PublicKey,
    PrivateKey,
    generate_key_pair,
    wallet_address_from_public_key,
)

class User:
    def __init__(self):
        keys = generate_key_pair()
        self.public_key = keys[0]
        self.private_key = keys[1]

    def get_address(self):
        return wallet_address_from_public_key(self.public_key)

    def send(self, to: 'User', amount: TransactionAmount) -> Transaction:
        from_wallet = self.get_address()
        to_wallet = to.get_address()
        t = Transaction(to_wallet, amount, from_wallet, self.public_key)
        self.sign_transaction(t)
        return t

    def mine(self) -> Transaction:
        return Transaction(self.get_address(), PDN(50))

    def get_public_key(self) -> PublicKey:
        return self.public_key

    def get_private_key(self) -> PrivateKey:
        return self.private_key

    def sign_transaction(self, t: Transaction):
        t.sign(self.public_key, self.private_key)
