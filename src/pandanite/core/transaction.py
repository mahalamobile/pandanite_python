from typing import Dict, List, Optional, Deque, cast
from collections import deque
import copy
import ed25519
from pandanite.core.crypto import (
    PublicWalletAddress,
    PublicKey,
    PrivateKey,
    SHA256Hash,
    NULL_SHA256_HASH,
    NULL_ADDRESS,
    TransactionSignature,
    sha_256,
    sha_256_to_string,
    wallet_address_to_string,
    string_to_wallet_address,
    string_to_signature,
    string_to_public_key,
    public_key_to_string,
    signature_to_string,
    sign_with_private_key_bytes,
    check_signature_bytes,
    concat_hashes,
    hex_encode,
    wallet_address_from_public_key,
)
from pandanite.core.common import TransactionAmount


class Transaction:
    def __init__(
        self,
        to_wallet: PublicWalletAddress = NULL_ADDRESS,
        amount: Optional[TransactionAmount] = None,
        signing_key: Optional[PublicKey] = None,
        fee: TransactionAmount = 0,
        timestamp: int = 0,
    ):
        self.signature: Optional[TransactionSignature] = None
        self.signing_key: PublicKey = copy.deepcopy(signing_key)
        self.timestamp = timestamp
        self.to: PublicWalletAddress = copy.deepcopy(to_wallet)
        self.amount: TransactionAmount = amount if amount else 0
        self.fee: TransactionAmount = fee

    def from_json(self, data: Dict):
        self.timestamp = int(data["timestamp"])
        self.to = string_to_wallet_address(data["to"])
        self.fee = data["fee"]
        self.amount = data["amount"]
        if "signingKey" in data.keys():
            self.signature = string_to_signature(data["signature"])
            self.signing_key = string_to_public_key(data["signingKey"])

    def to_json(self):
        result = {}
        result["to"] = wallet_address_to_string(self.to)
        result["amount"] = self.amount
        result["timestamp"] = str(self.timestamp)
        result["fee"] = self.fee
        result["txid"] = sha_256_to_string(self.hash_contents())
        if not self.is_fee():
            result["signingKey"] = public_key_to_string(self.signing_key)
            result["signature"] = signature_to_string(self.signature)
        return result

    def copy(self) -> "Transaction":
        return copy.deepcopy(self)

    def set_transaction_fee(self, amount: TransactionAmount):
        self.fee = amount

    def get_transaction_fee(self) -> TransactionAmount:
        return self.fee

    def get_sender(self) -> PublicWalletAddress:
        return wallet_address_from_public_key(self.signing_key)

    def set_amount(self, amt: TransactionAmount):
        self.amount = amt

    def get_signing_key(self) -> PublicKey:
        return self.signing_key

    def get_amount(self) -> TransactionAmount:
        return self.amount

    def get_fee(self) -> TransactionAmount:
        return self.fee

    def get_recepient(self) -> PublicWalletAddress:
        return self.to

    def set_timestamp(self, t: int):
        self.timestamp = t

    def get_timestamp(self) -> int:
        return self.timestamp

    def get_hash(self) -> SHA256Hash:
        hash = self.hash_contents()
        if not self.is_fee():
            if not self.signature:
                raise Exception("Tried to get hash of unsigned transaction")
            hash += self.signature
        return sha_256(hash)

    def hash_contents(self) -> SHA256Hash:
        buf = bytearray()
        buf += self.to
        if not self.is_fee():
            buf += wallet_address_from_public_key(self.signing_key)
        buf += (
            self.fee.to_bytes(8) + self.amount.to_bytes(8) + self.timestamp.to_bytes(8)
        )
        ret = sha_256(buf)
        return ret

    def sign(self, private_key: PrivateKey):
        hash = self.hash_contents()
        signature = sign_with_private_key_bytes(bytes(hash), private_key)
        self.signature = signature

    def get_signature(self) -> TransactionSignature:
        if not self.signature:
            raise Exception("Tried to read signature of unsigned transaction")
        return self.signature

    def signature_valid(self) -> bool:
        if self.is_fee():
            return True
        hash = self.hash_contents()
        return check_signature_bytes(bytes(hash), self.signature, self.signing_key)

    def is_fee(self) -> bool:
        return self.signing_key == None

    def __eq__(self, other):
        if isinstance(other, Transaction):
            ret = (
                self.signature == other.signature
                and self.timestamp == other.timestamp
                and self.to == other.to
                and self.signing_key == other.signing_key
                and self.amount == other.amount
                and self.fee == other.fee
                and self.is_fee() == other.is_fee()
            )
            return ret
        return False


# merkle proofs
class Node:
    def __init__(self, hash: SHA256Hash):
        self.hash = hash
        self.parent: Optional[Node] = None
        self.left: Optional[Node] = None
        self.right: Optional[Node] = None


def get_merkle_hash(items: List[Transaction]) -> SHA256Hash:
    fringe_nodes: Dict[bytearray, Node] = {}
    items.sort(key=lambda a: sha_256_to_string(a.get_hash()), reverse=True)

    q: Deque[Node] = deque()

    for item in items:
        h = item.get_hash()
        fringe_nodes[h] = Node(h)
        q.append(fringe_nodes[h])

    if len(q) % 2 == 1:
        repeat = Node(q[-1].hash)
        q.append(repeat)

    while len(q) > 1:
        a: Node = q.popleft()
        b: Node = q.popleft()
        root = Node(NULL_SHA256_HASH)
        root.left = a
        root.right = b
        a.parent = root
        b.parent = root
        root.hash = concat_hashes(a.hash, b.hash)
        q.append(root)

    return q[0].hash
