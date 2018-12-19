import yaml
import json
import uuid
from . import bigfix_to_stix_translator
from ...base.base_result_translator import BaseResultTranslator
from stix_shifter.stix_translation.src import transformers

class BigFixToStix(BaseResultTranslator):

    def translate_results(self, data_source, data, options, mapping=None):
        """
        Translates JSON data into STIX results based on a mapping file
        :param data: JSON formatted data to translate into STIX format
        :type data: str
        :param mapping: The mapping file path to use as instructions on how to translate the given JSON data to STIX. Defaults the path to whatever is passed into the constructor for JSONToSTIX (This should be the to_stix_map.json in the module's json directory)
        :type mapping: str (filepath)
        :return: STIX formatted results
        :rtype: str
        """
        self.mapping_json = options.get('mapping', {})
        
        # result_data = data.replace('\"isFailure\": False', '\"isFailure\": \"False\"')
        # json_data = json.loads(result_data)
        # json library fails to load the data so we are using yaml library (YAML is a superset of JSON)
        json_data = yaml.load(data)
        data_source = json.loads(data_source)

        if(not self.mapping_json):
            map_file = open(self.default_mapping_file_path).read()
            map_data = json.loads(map_file)
        else:
            map_data = self.mapping_json

        results = bigfix_to_stix_translator.convert_to_stix(data_source, map_data, 
                                                        json_data, transformers.get_all_transformers(), options)
         
        return json.dumps(results, indent=4, sort_keys=False)