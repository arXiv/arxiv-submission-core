"""
Integration with the classic classifier service.

The classifier analyzes the text of the specified paper and returns
a list of suggested categories based on similarity comparisons performed
between the text of the paper and statistics for each category.

Typically used to evaluate article classification prior to review by
moderators.

Unlike the original arXiv::Classifier module, this module contains no real
business-logic: the objective is simply to provide a user-friendly calling
API.
"""

from .classifier import Classifier
