from typing import List, Dict, Any
from pymongo import MongoClient
from pandanite.logging import logger
from pandanite.core.transaction import Transaction
from pandanite.core.crypto import (
    SHA256Hash,
    add_work,
    PublicWalletAddress,
    NULL_SHA256_HASH,
    wallet_address_to_string,
)
from pandanite.core.common import TransactionAmount
from pandanite.core.block import Block

"""'
Mongo collection schemas
blocks: Results of block.to_json() are stored directly
transaction_to_block: { 'tx_id': string, 'block_id': int }
ledger: {'address': string, 'balance': int }
wallet_to_transaction: {'address': string, 'tx_ids': list[string]}
info: {'total_work': int, 'difficulty': int, 'num_blocks': int}
"""


class PandaniteDB:
    def __init__(self, port: int = 27017, db: str = "pandanite-test", clear=True):
        self.client = MongoClient("localhost", port)
        self.db = self.client[db]
        self.transaction_to_block = self.db.transaction_to_block
        self.transaction_to_block.create_index("tx_id", unique=True)
        self.blocks = self.db.blocks
        self.blocks.create_index("id", unique=True)
        self.ledger = self.db.ledger
        self.ledger.create_index("address", unique=True)
        self.wallet_to_transaction = self.db.wallet_to_transaction
        self.wallet_to_transaction.create_index("address", unique=True)
        self.info = self.db.info
        if clear:
            self.clear()

    def clear(self):
        self.transaction_to_block.drop()
        self.blocks.drop()
        self.ledger.drop()
        self.wallet_to_transaction.drop()
        self.info.drop()
        self.info.replace_one(
            {},
            {
                "total_work": str(0),
                "num_blocks": 0,
                "difficulty": 16,
            },
            upsert=True,
        )

    def set_difficulty(self, difficulty: int):
        info = self.info.find_one({})
        self.info.replace_one(
            {},
            {
                "total_work": info["total_work"],
                "num_blocks": info["num_blocks"],
                "difficulty": difficulty,
            },
            upsert=True,
        )

    def get_num_blocks(self) -> int:
        return self.info.find_one({})["num_blocks"]

    def get_total_work(self) -> int:
        return int(self.info.find_one()["total_work"])

    def get_difficulty(self) -> int:
        return self.info.find_one()["difficulty"]

    def add_block(self, block: Block):
        self.blocks.replace_one({"id": block.get_id()}, block.to_json(), upsert=True)
        for t in block.get_transactions():
            self.transaction_to_block.replace_one(
                {"tx_id": t.get_id()},
                {"tx_id": t.get_id(), "block_id": block.get_id()},
                upsert=True,
            )
        info = self.info.find_one({})
        new_work = add_work(int(info["total_work"]), block.get_difficulty())
        self.info.replace_one(
            {},
            {
                "total_work": str(new_work),
                "num_blocks": block.get_id(),
                "difficulty": block.get_difficulty(),
            },
            upsert=True,
        )

    def start_session(self):
        return self.client.start_session()

    def get_wallets(
        self, wallets: list[PublicWalletAddress]
    ) -> Dict[str, TransactionAmount]:
        wallet_totals: Dict[str, TransactionAmount] = {}
        for wallet in wallets:
            wallet_address = wallet_address_to_string(wallet)
            found_wallet = self.ledger.find_one({"address": wallet_address})
            if found_wallet:
                wallet_totals[wallet_address] = found_wallet["balance"]
        return wallet_totals

    def block_for_transaction(self, t: Transaction) -> int:
        found_tx = self.transaction_to_block.find_one({"tx_id": t.get_id()})
        if found_tx != None:
            return found_tx["block_id"]
        else:
            return -1

    def update_wallet(self, wallet: str, amount: TransactionAmount):
        updated_record = {
            "address": wallet,
            "balance": amount,
        }
        self.ledger.replace_one({"address": wallet}, updated_record, upsert=True)

    def add_wallet_transaction(self, wallet: PublicWalletAddress, tx_id: str):
        address = wallet_address_to_string(wallet)
        self.wallet_to_transaction.update_one(
            {"address": address}, {"$push": {"tx_ids": tx_id}}, upsert=True
        )

    def remove_wallet_transaction(self, wallet: PublicWalletAddress, tx_id: str):
        address = wallet_address_to_string(wallet)
        self.wallet_to_transaction.update_one(
            {"address": address}, {"$pull": {"tx_ids": tx_id}}, upsert=True
        )

    def pop_block(self):
        # TODO remove actual block from mongo collection
        return None

    def find_block_for_transaction(self, t: Transaction) -> int:
        return 0

    def find_block_for_transaction_id(self, txid: SHA256Hash) -> int:
        return 0

    def get_transactions_for_wallet(
        self, addr: PublicWalletAddress
    ) -> List[Transaction]:
        return []

    def get_last_hash(self) -> SHA256Hash:
        count = self.get_num_blocks()
        if count == 0:
            return NULL_SHA256_HASH
        return self.get_block(count).get_hash()

    def get_block(self, block_id: int) -> Block:
        if block_id <= 0 or block_id > self.get_num_blocks():
            raise Exception("Invalid block")
        b = Block()
        b.from_json(self.blocks.find_one({"id": block_id}))
        return b
