"""
Enhanced Tag Processing Engine
Handles all #TAG# replacements defined in the requirements.
"""
import html as html_lib
import itertools
import random
import re
import string
import uuid
from datetime import datetime
from typing import Dict, List, Optional


class TagProcessor:
    """
    Replaces all #TAG# tokens in text/HTML content.
    Tags supported:
      #TFN1#, #TFN2#, #DATE#, #TIME#, #EMAIL#, #NAME#, #USER#, #MAILRANDOM#,
      #INVOICE#, #ORDERID#, #TXNID#, #TYPE#, #AMOUNT#,
      #KEY#, #GUID#, #SNUMBER#, #ADDRESS#, #SENDER#, #NUMBER9#
    """

    _UNSUB_MARKER = "__PROMAILER_UNSUB_MARKER__"
    _OPT_OUT_SENTENCE_RE = re.compile(
        r'^(?:'
        r'(?:if\s+you\s+(?:do\s+not|don[\'\u2019]?t|no\s+longer)\s+(?:wish|want)\s+to\s+receive\b[^.]*?)'
        r'|(?:(?:don[\'\u2019]?t|do\s+not)\s+want\s+to\s+receive\b[^.]*?)'
        r'|(?:to\s+(?:unsubscribe|opt[\s-]*out|stop\s+receiving)\b[^.]*?)'
        r'|(?:(?:please\s+)?click\s+(?:here\s+)?to\s+(?:unsubscribe|opt[\s-]*out)\b[^.]*?)'
        r'|(?:(?:you\s+may|you\s+can)\s+(?:(?:click\s+(?:here\s+)?)?(?:to\s+)?)?(?:unsubscribe|opt[\s-]*out|manage\s+(?:your\s+)?(?:email\s+)?preferences)?\s*(?:here)?)'
        r'|(?:(?:manage\s+(?:email\s+)?preferences|email\s+preferences|unsubscribe|opt[\s-]*out)'
        r'(?:\s+(?:from|link|url|here|emails?|notifications?|messages?|future|anytime|at|time))*\s*[:\-–—]?)'
        r')?\s*'
        r'__PROMAILER_UNSUB_MARKER__'
        r'(?:\s*(?:from\s+future\s+[\w\s]+|from\s+(?:this|our)\s+[\w\s]+|to\s+(?:unsubscribe|opt[\s-]*out|manage\s+[\w\s]+)|at\s+any\s+time|anytime))?'
        r'[\s.!|•·\-–—]*$',
        re.IGNORECASE,
    )

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
        # TXN-Random 9 Character Transaction ID
        mix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))
        return f"TXN-{mix}"

    @staticmethod
    def _rand_key() -> str:
        return str(uuid.uuid4()).lower()

    @staticmethod
    def _rand_guid() -> str:
        return str(uuid.uuid4()).lower()

    @staticmethod
    def _rand_number() -> str:
        # Randomly 8 series Number (8 digits)
        return str(random.randint(10000000, 99999999))

    @staticmethod
    def _rand_random() -> str:
        # Randomly generated 11 Series Number and alphabet Capital (e.g. 6WA5KQ7G8T2)
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=11))

    @staticmethod
    def _rand_serial() -> str:
        return str(random.randint(10000000, 99999999))

    @staticmethod
    def _rand_snumber() -> str:
        return str(random.randint(1000000, 9999999))

    @staticmethod
    def _rand_number9() -> str:
        # Always Start with 9 - formatted like (9XX-XX-XXXX)
        b1 = "".join(random.choices(string.digits, k=2))
        b2 = "".join(random.choices(string.digits, k=2))
        b3 = "".join(random.choices(string.digits, k=4))
        return f"9{b1}-{b2}-{b3}"

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
        if mode == "custom" and custom and str(custom).strip():
            return str(custom).strip()
        cents = random.randint(int(min_val * 100), int(max_val * 100))
        return f"{cents / 100:.2f}"

    def _date_str(self) -> str:
        fmt = random.choice(self.DATE_FORMATS)
        return datetime.now().strftime(fmt)

    def build_replacements(self, recipient: Dict, campaign_tags: Optional[Dict] = None, sender_name: str = "", sender_email: str = "", include_unsubscribe: bool = True) -> Dict[str, str]:
        """
        Build the dictionary of tag replacements for a recipient.
        Calling this once per recipient ensures identical values (e.g. invoice, amount, date)
        can be applied consistently across email subject, body HTML, and PDF attachment.
        """
        if campaign_tags is None:
            campaign_tags = {}

        email = recipient.get("email", "") if recipient else ""
        name  = recipient.get("name", "") if recipient else ""
        user  = email.split("@")[0] if email and "@" in email else (email or "")
        if not name and email:
            name = user

        # Per-email random values
        invoice      = self._rand_invoice()
        orderid      = self._rand_orderid()
        txnid        = self._rand_txnid()
        key          = self._rand_key()
        guid         = self._rand_guid()
        number       = self._rand_number()
        number9      = self._rand_number9()
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

        # #MAILRANDOM#: Email First Portion + Random 4 or 5 digit
        mail_random = f"{user}{random.choice([random.randint(1000, 9999), random.randint(10000, 99999)])}"

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

        # Sender username prefix before @
        # Example: 'janat meeyah <janatdmkmeeyah@outlook.com>' -> 'janatdmkmeeyah'
        clean_s_email = sender_email.strip() if sender_email else ""
        if "<" in clean_s_email and ">" in clean_s_email:
            clean_s_email = clean_s_email.split("<")[1].split(">")[0].strip()
        sender_user = clean_s_email.split("@")[0].strip() if "@" in clean_s_email else (clean_s_email or (sender_name or ""))

        # Unsubscribe link (points to promailer cloud server if license key available, else mailto fallback)
        if not include_unsubscribe:
            unsub_link = ""
        else:
            custom_unsub = campaign_tags.get("custom_unsubscribe_url", "").strip()
            lic_key = campaign_tags.get("license_key", "").strip()
            cust_name = ""
            if not lic_key:
                try:
                    from backend.database import Database
                    from backend.license_validator import verify_token
                    _db = Database()
                    tok = _db.get_setting("license_token", default="")
                    if tok:
                        _p = verify_token(tok)
                        lic_key = (_p.get("license_key") or "").strip()
                        cust_name = (_p.get("customer_name") or "").strip()
                except Exception:
                    pass

            active_lic = cust_name or lic_key or "Pooja"

            import urllib.parse
            encoded_email = urllib.parse.quote(email) if email else ""
            encoded_lic = urllib.parse.quote(active_lic)

            if custom_unsub:
                unsub_link = custom_unsub.replace("#EMAIL#", encoded_email).replace("#USER#", user)
            elif email:
                unsub_link = f"https://promailer-licensing.diracai.com/unsubscribe?lic={encoded_lic}&email={encoded_email}"
            else:
                target_sender = sender_email if sender_email else "optout@domain.com"
                unsub_link = f"mailto:{target_sender}?subject=Unsubscribe%20Request&body=Please%20unsubscribe%20my%20email:%20{email}"

        return {
            "#TFN1#": tfn1,
            "#TFN2#": tfn2,
            "#TFN#": tfn_val,
            "#DATE#": date_str,
            "#TIME#": time_str,
            "#EMAIL#": email,
            "#NAME#": name,
            "#USER#": user,
            "#MAILRANDOM#": mail_random,
            "#INVOICE#": invoice,
            "#ORDERID#": orderid,
            "#TXNID#": txnid,
            "#TYPE#": pay_type,
            "#AMOUNT#": amount,
            "#KEY#": key,
            "#GUID#": guid,
            "#NUMBER#": number,
            "#NUMBER9#": number9,
            "#RANDOM#": random_mix,
            "#SERIAL#": serial,
            "#SNUMBER#": snumber,
            "#ORDER#": order,
            "#LETTERS#": letters,
            "#LICENSE#": license_key,
            "#REGARDS#": regards,
            "#ADDRESS#": address,
            "#SENDER_EMAIL#": sender_email,
            "#SENDER#": sender_user,
            "#UNSUBSCRIBE#": unsub_link,
        }

    @staticmethod
    def without_unsubscribe(replacements: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Return a copy of replacements with #UNSUBSCRIBE# cleared for attachments."""
        if not replacements:
            return {}
        sanitized = dict(replacements)
        sanitized["#UNSUBSCRIBE#"] = ""
        return sanitized

    @classmethod
    def _is_pure_unsub_fragment(cls, raw_inner: str) -> bool:
        """Return True only when raw_inner has no real invoice/media content beyond opt-out boilerplate."""
        marker = cls._UNSUB_MARKER
        if marker not in raw_inner:
            return False
        if re.search(r'<(?:img|svg|table)\b', raw_inner, re.IGNORECASE):
            return False
        if re.search(r'#[A-Za-z0-9_]+#', raw_inner):
            return False

        plain = re.sub(r'<[^>]+>', ' ', raw_inner)
        plain = html_lib.unescape(plain).replace('\xa0', ' ')
        plain = re.sub(r'\s+', ' ', plain).strip()
        if not plain:
            return False

        without_marker = plain.replace(marker, '').strip()
        if len(without_marker) > 160:
            return False

        if not re.sub(r'[\s.,:;!|•·\-–—/()\[\]]+', '', without_marker):
            return True

        return bool(cls._OPT_OUT_SENTENCE_RE.match(plain))

    @classmethod
    def strip_unsubscribe_for_attachment(cls, text: str) -> str:
        """
        Strip #UNSUBSCRIBE# tags, anchor links, and dedicated opt-out footer blocks
        when rendering PDF/Image attachments or attachment filenames.
        Email body templates continue to resolve #UNSUBSCRIBE# normally.
        """
        if not text or "#unsubscribe#" not in text.lower():
            return text

        # Plain text / attachment filename pattern (no HTML markup)
        if "<" not in text or ">" not in text:
            cleaned = re.sub(r'#UNSUBSCRIBE#', '', text, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s*(?:\||•|·)\s*$', '', cleaned)
            cleaned = re.sub(r'^\s*(?:\||•|·)\s*', '', cleaned)
            cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
            return cleaned.strip()

        marker = cls._UNSUB_MARKER
        result = text

        # 1. Replace <a ...>...</a> anchor elements referencing #UNSUBSCRIBE# with marker
        result = re.sub(
            r'<a\b(?:(?!</a\s*>|<a\b).)*?#UNSUBSCRIBE#(?:(?!</a\s*>|<a\b).)*?</a\s*>',
            marker,
            result,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # 2. Strip #UNSUBSCRIBE# inside non-anchor HTML tag attributes (skip comments), then mark text occurrences
        result = re.sub(
            r'<(?!!--)[^>]*>',
            lambda m: re.sub(r'#UNSUBSCRIBE#', '', m.group(0), flags=re.IGNORECASE),
            result,
        )
        result = re.sub(r'#UNSUBSCRIBE#', marker, result, flags=re.IGNORECASE)

        if marker not in result:
            return result

        # 3. Bottom-up cleanup of dedicated leaf elements containing only opt-out text / marker
        leaf_pattern = re.compile(
            r'<(?P<tag>p|div|span|li|small|em|i|b|strong|font|footer)\b[^>]*>'
            r'(?P<inner>(?:(?!</?(?:p|div|span|li|small|em|i|b|strong|font|footer|table|tr|td|th|ul|ol)\b).)*?)'
            r'</(?P=tag)\s*>',
            re.IGNORECASE | re.DOTALL,
        )
        for _ in range(4):
            def _collapse_leaf(m):
                inner = m.group("inner")
                if cls._is_pure_unsub_fragment(inner):
                    return marker
                return m.group(0)

            updated = leaf_pattern.sub(_collapse_leaf, result)
            if updated == result:
                break
            result = updated

        # 4. Remove table rows whose only content was removed/empty opt-out cells
        tr_pattern = re.compile(
            r'<tr\b[^>]*>(?P<inner>(?:(?!</?(?:table|tr)\b).)*?)</tr>',
            re.IGNORECASE | re.DOTALL,
        )
        cell_pattern = re.compile(r'<t[dh]\b[^>]*>(?P<cinner>.*?)</t[dh]\s*>', re.IGNORECASE | re.DOTALL)

        def _strip_empty_tr(m):
            tr_inner = m.group("inner")
            if marker not in tr_inner:
                return m.group(0)
            cells = list(cell_pattern.finditer(tr_inner))
            if not cells:
                return m.group(0)
            for cm in cells:
                cinner = cm.group("cinner")
                if re.search(r'<(?:img|svg|table)\b', cinner, re.IGNORECASE):
                    return m.group(0)
                if marker in cinner:
                    if not cls._is_pure_unsub_fragment(cinner):
                        return m.group(0)
                else:
                    plain_cell = html_lib.unescape(re.sub(r'<[^>]+>', ' ', cinner)).replace('\xa0', ' ').strip()
                    if plain_cell:
                        return m.group(0)
            return ""

        result = tr_pattern.sub(_strip_empty_tr, result)

        # 5. Remove <br> + opt-out segment containing marker (both "<br> opt-out marker" and "opt-out marker <br>")
        br_after_re = re.compile(r'(<br\s*/?>)([^<\n]*?' + re.escape(marker) + r'[^<\n]*)', re.IGNORECASE)

        def _clean_after_br(m):
            if cls._is_pure_unsub_fragment(m.group(2)):
                return ""
            return m.group(0)

        result = br_after_re.sub(_clean_after_br, result)

        br_before_re = re.compile(r'([^>\n]*?' + re.escape(marker) + r'[^>\n]*?)(<br\s*/?>)', re.IGNORECASE)

        def _clean_before_br(m):
            if cls._is_pure_unsub_fragment(m.group(1)):
                return ""
            return m.group(0)

        result = br_before_re.sub(_clean_before_br, result)

        # 6. Clean inline opt-out clauses next to marker, standalone lines, or inline separators, then strip leftover marker
        sep_token = r'(?:\||&bull;|&#8226;|•|·|—)'
        optout_phrase = (
            r'(?:'
            r'if\s+you\s+(?:do\s+not|don[\'\u2019]?t|no\s+longer)\s+(?:wish|want)\s+to\s+receive[^.<>\n#]{0,120}?'
            r'|(?:don[\'\u2019]?t|do\s+not)\s+want\s+to\s+receive[^.<>\n#]{0,120}?'
            r'|to\s+(?:unsubscribe|opt[\s-]*out|stop\s+receiving)[^.<>\n#]{0,80}?'
            r'|(?:please\s+)?click\s+(?:here\s+)?to\s+(?:unsubscribe|opt[\s-]*out)[^.<>\n#]{0,60}?'
            r'|(?:you\s+may|you\s+can)\s+(?:(?:click\s+(?:here\s+)?)?(?:to\s+)?)?(?:unsubscribe|opt[\s-]*out|manage\s+(?:your\s+)?(?:email\s+)?preferences)?\s*(?:here)?'
            r'|(?:manage\s+(?:email\s+)?preferences|email\s+preferences|unsubscribe|opt[\s-]*out)'
            r'(?:\s+(?:from|link|url|here|emails?|notifications?|messages?|future|anytime|at|time))*\s*[:\-–—]?'
            r')'
        )
        post_optout = r'(?:\s*(?:from\s+future\s+[\w\s]+|from\s+(?:this|our)\s+[\w\s]+|to\s+(?:unsubscribe|opt[\s-]*out|manage\s+[\w\s]+)|at\s+any\s+time|anytime))?[.!?]*(?:\s+(?=<|$))?'

        # Opt-out clause preceded by a separator (e.g. "Support #TFN1# | Unsubscribe: MARKER")
        result = re.sub(
            r'\s*' + sep_token + r'\s*' + optout_phrase + r'\s*' + re.escape(marker) + post_optout,
            '',
            result,
            flags=re.IGNORECASE,
        )
        # Opt-out clause followed by a separator (e.g. "Unsubscribe: MARKER | Support #TFN1#")
        result = re.sub(
            optout_phrase + r'\s*' + re.escape(marker) + post_optout + r'\s*' + sep_token + r'\s*',
            '',
            result,
            flags=re.IGNORECASE,
        )
        # Opt-out sentence following previous sentence punctuation or start of text node (preserving '.', '!', '?')
        result = re.sub(
            r'(?:(?<=[.!?])|(?<=>)|^)\s*' + optout_phrase + r'\s*' + re.escape(marker) + post_optout,
            '',
            result,
            flags=re.IGNORECASE,
        )

        line_re = re.compile(r'^[ \t]*[^<>\n]*?' + re.escape(marker) + r'[^<>\n]*[ \t]*(?:\r?\n)?', re.MULTILINE)

        def _clean_line(m):
            if cls._is_pure_unsub_fragment(m.group(0)):
                return ""
            return m.group(0)

        result = line_re.sub(_clean_line, result)

        result = re.sub(
            r'(?:\s*(?:\||&bull;|&#8226;|•|·|—)\s*)' + re.escape(marker)
            + r'|' + re.escape(marker) + r'(?:\s*(?:\||&bull;|&#8226;|•|·|—)\s*)',
            '',
            result,
        )
        result = result.replace(marker, '')
        return result

    def apply_replacements(self, text: str, replacements: Dict[str, str]) -> str:
        """Replace all tags in text using the provided dictionary."""
        if not text:
            return text
        # Sort keys by length descending to prevent substring collisions (e.g. #SENDER_EMAIL# vs #SENDER#)
        for tag in sorted(replacements.keys(), key=len, reverse=True):
            text = text.replace(tag, str(replacements[tag]))
        return text

    # def process(self, text: str, recipient: Dict, campaign_tags: Optional[Dict] = None, sender_name: str = "") -> str:
    def process(self, text: str, recipient: Dict, campaign_tags: Optional[Dict] = None, sender_name: str = "", sender_email: str = "", replacements: Optional[Dict] = None) -> str:
        """
        Replace all tags in `text`.
        :param text: Raw text / HTML with #TAG# markers.
        :param recipient: Dict with 'email' and optional 'name'.
        :param campaign_tags: Dict with campaign-level settings from UI.
        :param sender_name: Configured/current sender regards line.
        :param sender_email: Current SMTP sender email address.
        :param replacements: Optional pre-built replacements dict to reuse across body and attachments.
        """
        if not text:
            return text
        if replacements is None:
            replacements = self.build_replacements(recipient, campaign_tags, sender_name, sender_email)
        return self.apply_replacements(text, replacements)
