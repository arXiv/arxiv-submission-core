"""Test abstract cleanup"""

from unittest import TestCase
from .. import SetAbstract
from arxiv.base.filters import abstract_lf_to_br

class TestSetAbstractCleanup(TestCase):
    """Test abstract cleanup"""

    def test_paragraph_cleanup(self):
        awlb = "Paragraph 1.\n  \nThis should be paragraph 2"
        self.assertIn('<br', abstract_lf_to_br(awlb),
                      'sanity check: abstract filter does put <br> in')

        e = SetAbstract(creator='xyz', abstract=awlb)
        self.assertIn('<br', abstract_lf_to_br(e.abstract),
                      '.cleanup must preserve <br> creating whitespace')

        awlb = "Paragraph 1.\n\t\nThis should be p 2."
        e = SetAbstract(creator='xyz', abstract=awlb)
        self.assertIn('<br', abstract_lf_to_br(e.abstract),
                      '.cleanup must preserve <br> creating whitespace (tab)')

        awlb = "Paragraph 1.\n  \nThis should be p 2."
        e = SetAbstract(creator='xyz', abstract=awlb)
        self.assertIn('<br', abstract_lf_to_br(e.abstract),
                      '.cleanup must preserve <br> creating whitespace')

        awlb = "Paragraph 1.\n \t \nThis should be p 2."
        e = SetAbstract(creator='xyz', abstract=awlb)
        self.assertIn('<br', abstract_lf_to_br(e.abstract),
                      '.cleanup must preserve <br> creating whitespace')

        awlb = "Paragraph 1.\n     \nThis should be p 2."
        e = SetAbstract(creator='xyz', abstract=awlb)
        self.assertIn('<br', abstract_lf_to_br(e.abstract),
                      '.cleanup must preserve <br> creating whitespace')

        awlb = "Paragraph 1.\n This should be p 2."
        e = SetAbstract(creator='xyz', abstract=awlb)
        self.assertIn('<br', abstract_lf_to_br(e.abstract),
                      '.cleanup must preserve <br> creating whitespace')

        awlb = "Paragraph 1.\n\tThis should be p 2."
        e = SetAbstract(creator='xyz', abstract=awlb)
        self.assertIn('<br', abstract_lf_to_br(e.abstract),
                      '.cleanup must preserve <br> creating whitespace')

        awlb = "Paragraph 1.\n  This should be p 2."
        e = SetAbstract(creator='xyz', abstract=awlb)
        self.assertIn('<br', abstract_lf_to_br(e.abstract),
                      '.cleanup must preserve <br> creating whitespace')
