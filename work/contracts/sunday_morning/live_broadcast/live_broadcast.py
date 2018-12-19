from iconservice import *


TAG = 'LiveBroadcast'


# An interface of ICON Token Standard, IRC-2
class TokenStandard(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def symbol(self) -> str:
        pass

    @abstractmethod
    def decimals(self) -> int:
        pass

    @abstractmethod
    def totalSupply(self) -> int:
        pass

    @abstractmethod
    def balanceOf(self, _owner: Address) -> int:
        pass

    @abstractmethod
    def transfer(self, _to: Address, _value: int, _data: bytes = None):
        pass


# An interface of tokenFallback.
# Receiving SCORE that has implemented this interface can handle
# the receiving or further routine.
class TokenFallbackInterface(InterfaceScore):
    @interface
    def tokenFallback(self, _from: Address, _value: int, _data: bytes):
        pass


class LiveBroadcast(IconScoreBase, TokenStandard):

    _VIDEOS         = 'videos'
    _BALANCES       = 'balances'
    _TOTAL_SUPPLY   = 'total_supply'
    _DECIMALS       = 'decimals'
    _ADMIN          = 'admin'

    def __init__(self, db: IconScoreDatabase) -> None:
        super().__init__(db)
        self._total_supply  = VarDB(self._TOTAL_SUPPLY, db, value_type=int)
        self._decimals      = VarDB(self._DECIMALS, db, value_type=int)
        self._balances      = DictDB(self._BALANCES, db, value_type=int)
        self._videos        = DictDB(self._VIDEOS, db, value_type=Address)  # hash(SHA256): str -> Address
        self._admin         = VarDB(self._ADMIN, db, value_type=Address)

    def on_install(self, _initialSupply: int, _decimals: int) -> None:
        super().on_install()

        if _initialSupply < 0:
            revert("Initial supply cannot be less than zero")

        if _decimals < 0:
            revert("Decimals cannot be less than zero")
        if _decimals > 21:
            revert("Decimals cannot be more than 21")

        total_supply = _initialSupply * 10 ** _decimals
        Logger.debug(f'on_install: total_supply={total_supply}', TAG)

        self._total_supply.set(total_supply)
        self._decimals.set(_decimals)
        self._balances[self.msg.sender] = total_supply
        self._videos["0x0000000000000000000000000000000000000000000000000000000000000000"] = self.msg.sender
        self._admin = self.msg.sender

    def on_update(self) -> None:
        super().on_update()

    @external(readonly=True)
    def name(self) -> str:
        return "LiveBroadcast"

    @external(readonly=True)
    def symbol(self) -> str:
        return "LB"

    @external(readonly=True)
    def decimals(self) -> int:
        return self._decimals.get()

    @external(readonly=True)
    def totalSupply(self) -> int:
        return self._total_supply.get()

    @external(readonly=True)
    def balanceOf(self, _owner: Address) -> int:
        return self._balances[_owner]

    @external
    def transfer(self, _to: Address, _value: int, _data: bytes = None):
        if _data is None:
            _data = b'None'
        self._transfer(self.msg.sender, _to, _value, _data)

    def _transfer(self, _from: Address, _to: Address, _value: int, _data: bytes):

        # Checks the sending value and balance.
        if _value < 0:
            revert("Transferring value cannot be less than zero")
        if self._balances[_from] < _value:
            revert("Out of balance")

        self._balances[_from] = self._balances[_from] - _value
        self._balances[_to] = self._balances[_to] + _value

        if _to.is_contract:
            # If the recipient is SCORE,
            #   then calls `tokenFallback` to hand over control.
            recipient_score = self.create_interface_score(_to, TokenFallbackInterface)
            recipient_score.tokenFallback(_from, _value, _data)

        Logger.debug(f'Transfer({_from}, {_to}, {_value}, {_data})', TAG)

    @external(readonly=True)
    def ownerOf(self, _hash: str) -> Address:
        return self._videos[_hash]

    @external
    def upload(self, _hash: str):
        self._upload(_hash, self.msg.sender)

    def _upload(self, _hash: str, _owner: Address):
        self._videos[_hash] = _owner

    # donation - auto-distribution
    @external
    def donation(self, _hash: str, _value: int, _data: bytes = None):
        if _data is None:
            _data = b'None'

        _from = self.msg.sender
        _to = self._videos[_hash]
        _fee = int(_value / 10)

        self._transfer(_from, _to, (_value - _fee), _data)
        self._transfer(_from, self._admin, _fee, _data)