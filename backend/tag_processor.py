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
        "Auto Debit ACH", "PayPal", "Visa/Master Card", "Auto Debit(Bank A/C)"
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
        # Return a premium-styled placeholder address if pool is empty to wow the user
        streets = ["Mill Street", "Oak Avenue", "Greenville Road", "Pine Street", "Maple Drive"]
        cities = ["Greenville, SC", "Dallas, TX", "Chicago, IL", "Charlotte, NC", "Austin, TX"]
        return f"{random.randint(1000, 9999)} {random.choice(streets)}, {random.choice(cities)} {random.randint(10000, 99999)}"

    @staticmethod
    def _rand_invoice() -> str:
        mix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        suffix = random.randint(10, 99)
        return f"INV-{mix}-{suffix}"

    @staticmethod
    def _rand_orderid() -> str:
        mix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))
        return f"ORD-{mix}"

    @staticmethod
    def _rand_txnid() -> str:
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

    @staticmethod
    def _rand_key() -> str:
        return str(uuid.uuid4()).lower()

    @staticmethod
    def _rand_guid() -> str:
        return str(uuid.uuid4()).lower()

    @staticmethod
    def _rand_number() -> str:
        return str(random.randint(100000000, 999999999))

    @staticmethod
    def _rand_random() -> str:
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=14))

    @staticmethod
    def _rand_serial() -> str:
        return str(random.randint(10000000, 99999999))

    @staticmethod
    def _rand_snumber() -> str:
        return str(random.randint(1000000, 9999999))

    @staticmethod
    def _rand_order() -> str:
        return str(random.randint(100000, 999999))

    @staticmethod
    def _rand_letters() -> str:
        return ''.join(random.choices(string.ascii_uppercase, k=15))

    @staticmethod
    def _rand_license() -> str:
        block1 = ''.join(random.choices(string.digits, k=4))
        block2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        block3 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"PRO-{block1}-{block2}-{block3}"

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

    def process(self, text: str, recipient: Dict, campaign_tags: Optional[Dict] = None, sender_name: str = "") -> str:
        """
        Replace all tags in `text`.
        :param text: Raw text / HTML with #TAG# markers.
        :param recipient: Dict with 'email' and optional 'name'.
        :param campaign_tags: Dict with campaign-level settings from UI.
        :param sender_name: Configured/current sender regards line.
        """
        if not text:
            return text

        if campaign_tags is None:
            campaign_tags = {}

        email = recipient.get("email", "")
        name  = recipient.get("name", "") or email.split("@")[0]

        # Per-email random values (generated once per call)
        invoice      = self._rand_invoice()
        orderid      = self._rand_orderid()
        txnid        = self._rand_txnid()
        key          = self._rand_key()
        guid         = self._rand_guid()
        number       = self._rand_number()
        random_mix   = self._rand_random()
        serial       = self._rand_serial()
        snumber      = self._rand_snumber()
        order        = self._rand_order()
        letters      = self._rand_letters()
        license_key  = self._rand_license()
        pay_type     = random.choice(self.PAYMENT_TYPES)
        amount       = self._rand_amount(
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

        tfn1 = campaign_tags.get("tfn1", "")
        tfn2 = campaign_tags.get("tfn2", "")
        if tfn1 and tfn2:
            tfn_val = f"{tfn1} / {tfn2}"
        elif tfn1:
            tfn_val = tfn1
        else:
            tfn_val = tfn2

        regards = sender_name if sender_name else "Alex John"

        replacements = {
            "#TFN1#": tfn1,
            "#TFN2#": tfn2,
            "#TFN#": tfn_val,
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
            "#NUMBER#": number,
            "#RANDOM#": random_mix,
            "#SERIAL#": serial,
            "#SNUMBER#": snumber,
            "#ORDER#": order,
            "#LETTERS#": letters,
            "#LICENSE#": license_key,
            "#REGARDS#": regards,
            "#ADDRESS#": address,
        }

        for tag, val in replacements.items():
            text = text.replace(tag, str(val))
        return text
