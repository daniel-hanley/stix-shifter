# ..base.base_translator import BaseTranslator
from stix_shifter.stix_translation.src.json_to_stix.json_to_stix import JSONToStix
from ..base.base_translator import BaseTranslator
from .cim_to_stix.cim_to_stix import CIMToStix
from .stix_to_splunk import StixToSplunk
from .splunk_utils import hash_type_lookup

from os import path


class Translator(BaseTranslator):

    def __init__(self):
        basepath = path.dirname(__file__)
        filepath = path.abspath(
            path.join(basepath, "json", "to_stix_map.json"))
        self.mapping_filepath = filepath
        self.result_translator = JSONToStix(filepath, hash_type_lookup)
        self.query_translator = StixToSplunk()
