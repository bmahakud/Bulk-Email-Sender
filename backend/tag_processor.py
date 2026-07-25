"""
Enhanced Tag Processing Engine
Handles all #TAG# replacements defined in the requirements.
"""
import random
import string
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import itertools


class TagProcessor:
    """
    Replaces all #TAG# tokens in text/HTML content.
    Tags supported:
      #TFN1#, #TFN2#, #DATE#, #TIME#, #EMAIL#, #NAME#,
      #INVOICE#, #ORDERID#, #TXNID#, #TYPE#, #AMOUNT#,
      #KEY#, #GUID#, #SNUMBER#, #ADDRESS#
    """

    PAYMENT_TYPES = [
        "Bank Transfer", "PayPal", "ACH", "Auto Debit",
        "Visa/Master Card", "Debit Card", "Credit Card"
    ]

    DATE_FORMATS = [
        "%B %d, %Y",       # June 29, 2026
        "%A %b %d, %Y",   # Monday Jun 29, 2026
        "%d %B %Y",        # 29 June 2026
    ]

    def __init__(self):
        self._address_pool: List[str] = []
        self._address_iter = None

    def set_address_pool(self, addresses: List[str]):
        self._address_pool = [a.strip() for a in addresses if a.strip()]
        self._address_iter = itertools.cycle(self._address_pool) if self._address_pool else None

    def _next_address(self) -> str:
        if self._address_iter:
            return next(self._address_iter)
        return ""

    @staticmethod
    def _rand_invoice() -> str:
        letters = ''.join(random.choices(string.ascii_uppercase, k=5))
        digits  = random.randint(1000, 9999)
        return f"INV-{letters[:2]}{str(datetime.now().year)[-2:]}{letters[2:]}-{digits}"

    @staticmethod
    def _rand_orderid() -> str:
        num  = random.randint(1000000, 9999999)
        year = datetime.now().year
        return f"{num}-{year}"

    @staticmethod
    def _rand_txnid() -> str:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=9))

    @staticmethod
    def _rand_key() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _rand_guid() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _rand_snumber() -> str:
        return str(random.randint(100000, 999999))

    @staticmethod
    def _rand_amount(mode: str = "random", custom: str = "200.00",
                     min_val: float = 100.0, max_val: float = 300.0) -> str:
        if mode == "custom":
            return custom
        cents = random.randint(int(min_val * 100), int(max_val * 100))
        return f"{cents / 100:.2f}"

    def _date_str(self) -> str:
        fmt = random.choice(self.DATE_FORMATS)
        return datetime.now().strftime(fmt)

    def process(self, text: str, recipient: Dict, campaign_tags: Dict) -> str:
        """
        Replace all tags in `text`.
        :param text: Raw text / HTML with #TAG# markers.
        :param recipient: Dict with 'email' and optional 'name'.
        :param campaign_tags: Dict with campaign-level settings from UI.
        """
        if not text:
            return text

        email = recipient.get("email", "")
        name  = recipient.get("name", "") or email.split("@")[0]

        # Per-email random values (generated once per call)
        invoice   = self._rand_invoice()
        orderid   = self._rand_orderid()
        txnid     = self._rand_txnid()
        key       = self._rand_key()
        guid      = self._rand_guid()
        snumber   = self._rand_snumber()
        pay_type  = random.choice(self.PAYMENT_TYPES)
        amount    = self._rand_amount(
            mode=campaign_tags.get("amount_mode", "random"),
            custom=campaign_tags.get("amount_custom", "200.00"),
            min_val=float(campaign_tags.get("amount_min", 100)),
            max_val=float(campaign_tags.get("amount_max", 300)),
        )

        # Date / time
        if campaign_tags.get("date_auto", True):
            date_str = self._date_str()
        else:
            date_str = campaign_tags.get("date_manual", datetime.now().strftime("%B %d, %Y"))

        if campaign_tags.get("time_auto", True):
            time_str = datetime.now().strftime("%I:%M %p")
        else:
            time_str = campaign_tags.get("time_manual", datetime.now().strftime("%I:%M %p"))

        address = self._next_address()

        replacements = {
            "#TFN1#": campaign_tags.get("tfn1", ""),
            "#TFN2#": campaign_tags.get("tfn2", ""),
            "#DATE#": date_str,
            "#TIME#": time_str,
            "#EMAIL#": email,
            "#NAME#": name,
            "#INVOICE#": invoice,
            "#ORDERID#": orderid,
            "#TXNID#": txnid,
            "#TYPE#": pay_type,
            "#AMOUNT#": amount,
            "#KEY#": key,
            "#GUID#": guid,
            "#SNUMBER#": snumber,
            "#ADDRESS#": address,
        }

        for tag, val in replacements.items():
            text = text.replace(tag, str(val))
        return text
