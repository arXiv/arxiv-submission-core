self._no_strange_characters(submission)
self._no_author_titles(submission)
self._starts_with_uppercase(submission)
self._balanced_brackets(submission)
if self.title.lower().startswith('title'):
    raise InvalidEvent(self, "Must not start with `title`")
self._balanced_quotes(submission)
if self.title.startswith(' ') or self.title.endswith(' '):
    raise InvalidEvent(self, "Must not start or end with spaces")
self._no_double_spaces(submission)
self._check_for_html(submission)
self._check_for_tex_junk(submission)
stylistic_checks(self, submission, self.title)

def _no_strange_characters(self, submission: Submission) -> None:
    """Check for odd characters."""
    for char in "#@":
        if char in self.title:
            raise InvalidEvent(self, f"Strange character: {char}")

def _no_author_titles(self, submission: Submission) -> None:
    """Check for author titles."""
    ptn = r"^\s*(prof|dr|professor|doctor|lecturer|mr)\s*$"
    m = re.match(ptn, self.title)
    if m:
        raise InvalidEvent(self, f"Author title found: {m.group(1)}")

def _starts_with_uppercase(self, submission: Submission) -> None:
    """
    Verify that the title starts with an upper character.

    There are some exceptions to this rule, however...
    """
    if self.title[0].islower():
        exceptions = r"^(p\-adic$|de$|alpha|beta|gamma|phi|tau)"
        if not re.match(exceptions, self.title):
            raise InvalidEvent(self,
                               "Must not start with a lowercase character")

def _balanced_brackets(self, submission: Submission) -> None:
    """Curly brackets must be balanced, and not enclose the whole title."""
    if re.match(r"^[^\{]*\}", self.title):
        raise InvalidEvent("Contains unbalanced }")
    if re.match(r"\{[^\}]*$", self.title):
        raise InvalidEvent("Contains unbalanced {")
    if re.match(r"^\s*\{", self.title) and re.match(r"\}\s*$", self.title):
        raise InvalidEvent("Must not be wrapped in brackets ({})")

def _balanced_quotes(self, submission: Submission) -> None:
    """Verify that quotation marks are balanced."""
    m = re.search(r"\`\`(.+)\'\'", self.title)
    if m:
        raise InvalidEvent(self, f"Unbalanced quotes around {m.group(1)}")

def _no_double_spaces(self, submission: Submission) -> None:
    """Verify that no double-spaces are present."""
    if re.search(r"[\s]{2,}", self.title):
        raise InvalidEvent(self, "Contains multiple consecutive spaces")

def _capitalized_words(self, submission: Submission) -> None:
    """Check for unreasonable capitalization."""
    for word in self.title.split():
        if len(word) < 6:
            continue
        if word.isupper() and word not in ACCEPTABLE_CAPITALIZATIONS:
            raise InvalidEvent(self, f"Excessive capitalization: {word}")



def _check_for_tex_junk(self, submission: Submission) -> None:
    """Check for TeX junk."""
    if re.match(r"^\s*\{.{,7}|.{,7}\}\s*$", self.title):
        raise InvalidEvent(self, "Contains TeX junk")


def stylistic_checks(event: Event, submission: Submission, value: str) -> None:
    """
    Apply a wide range of stylistic checks on ``value``.

    These are from arXiv::Submit::MetaCheck.absfix.
    """
    # TODO: do we need to enforce chars in ([^\012\015\040-\177]) ?
    PATTERNS = [
        # We don't like tildes in astronomical catalog identifiers.
        (r"(NGC|UGC|SN)~(\d+)", "Remove ~ between %s and %s"),
        (r"(GRO)~", "Remove ~ after GRO"),
        # Nor in front of citations.
        (r"~(\\cite\{)", "Remove ~ in front of %s"),
        # Nor in quantities.
        (r"\b(\d+\}?\$?)~(MeV|GeV|TeV|keV|PeV|eV)\b",
         "Remove ~ between %s and %s"),
        # Check for TeX linebreaks.
        (r"(\\\\)", "TeX linebreaks (%s) are not allowed"),
        # Some other strange things we don't like.
        (r"\\\/", "Remove \/"),
        (r"\\([loO]) ", "Possible error, change to \{\\%s\}?"),
        (r"\\([vcu]) ([A-Za-z])", "TeX accents with space: %s %s"),
        (r"(\\[\'\"]\\[ij]) ", "Incorrect ij with acute etc. change: \{%s\}?"),
        # Look for extraneous $.
        (r"\$(d|s|p)\$-(wave|state)", f"unnecessary \$ change to %s-%s"),
        # Check for tildes in some idiosyncratic cases...
        (r"(Phys.~Rev.~Lett)", "Remove ~ from %s"),
        (r"(de~Sitter)", "Remove ~ from %s"),
        (r"\b(et~al)\b", "Remove ~ from %s"),
        (r"(i\.e\.~)", "Remove ~ from %s"),
        (r" ( e \. g \. ~ ) ", "Remove ~ from %s"),
        # Abbreviation style...
        (r"(\\ie\b)", "Change %s to i.e."),
        (r"(\\eg\b)", "Change %s to e.g."),
        (r"(\\etal\b)", "Change %s to et al"),
        (r"R--parity", "Remove extra - from R-parity"),
        (r"X--ray", "Remove extra - from X-ray"),
        # What the heck are these all about?
        (r"(^|\s)\*([\w\-]+)\*(\s|$)", "Remove ascii emphasis from %s%s%s"),
        (r"\b(\w+)\.(STY|TEX)\b", "Change to \L%s.%s\E "),
        (r"\$(-?\d+)\/([A-Z])\$", "Remove %s in front of %s"),

        # More weird TeXisms.
        (r" (Large) - \$N \$", "Remove \$ after %s around N "),
        (r"\\vert", "Convert vert to |"),
        (r"(\\<)", "Remove tex tabbing: %s"),
        (r"(\\>)", "Remove tex tabbing: %s"),
        (r"\\overline", "Change overline to bar"),
        (r"\\widehat", "Change widehat to hat"),
        (r"\{\\mbox(\{[^\{\}]+\})\}", "Remove \{mbox ... \} from %s"),
        #  \, \; \<space>  -->  <space>
        (r"(\.\.\.\.)\\( |,|;)(\.\.\.\.)", "Unescape character: %s\\%s%s"),
        (r"\`\`.*\"", "Inconsistent quotes"),
        (r"\\lq\b", "Change lq to real quote"),
        # Here are some common mipsellings...
        (r"\bpostcript", "postscript misspelled"),
        (r"\bmissprint", "misprint misspelled"),
        # More weird stuff.
        (r"\\(left|right)\|", "remove %s in front of |"),
        (r"\\\(", "Remove \ in front of ("),
        (r"\\\)", "Remove \ in front of )"),
        # Should not have a space before a subscript _
        (r"( +_)", "Remove space before subscript: %s"),
        (r"\'\'", "Change two single quotes to double quotes")
    ]
    for pattern, message in PATTERNS:
        match = re.search(pattern, value)
        if match:
            logger.error("Failed pattern `%s`: %s", pattern, value)
            raise InvalidEvent(event, message % match.groups())
