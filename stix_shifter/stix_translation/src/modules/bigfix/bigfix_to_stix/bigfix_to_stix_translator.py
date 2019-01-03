import re
import logging
import uuid
from stix2validator import validate_instance, print_results
from . import observable

def convert_to_stix(data_source, map_data, data, transformers, options):
    
    bundle = {
        "type": "bundle",
        "id": "bundle--" + str(uuid.uuid4()),
        "objects": []
    }

    identity_id = data_source['id']
    bundle['objects'] += [data_source]

    ds2stix = DataSourceObjToStixObj(identity_id, map_data, transformers, options)
    
    results = list(map(ds2stix.transform, data))
    for obj in results:
        if obj is not None:
            bundle["objects"].append(obj)

    return bundle

class DataSourceObjToStixObj:

    def __init__(self, identity_id, ds_to_stix_map, transformers, options):
        self.identity_id = identity_id
        self.ds_to_stix_map = ds_to_stix_map
        self.transformers = transformers

        # parse through options
        self.stix_validator = options.get('stix_validator', False)
        self.cybox_default = options.get('cybox_default', True)

        self.properties = observable.properties

    @staticmethod
    def _get_value(obj, ds_key, transformer):
        """
        Get value from source object, transforming if specified

        :param obj: the input object we are translating to STIX
        :param ds_key: the property from the input object
        :param transformer: the transform to apply to the property value (can be None)
        :return: the resulting STIX value
        """
        if ds_key not in obj:
            logging.debug('{} not found in object'.format(ds_key))
            return None
        ret_val = obj[ds_key]
        if transformer is not None:
            return transformer.transform(ret_val)
        return ret_val

    @staticmethod
    def _add_property(obj, key, stix_value):
        """
        Add stix_value to dictionary based on the input key, the key can be '.'-separated path to inner object

        :param obj: the dictionary we are adding our key to
        :param key: the key to add 
        :param stix_value: the STIX value translated from the input object
        """

        split_key = key.split('.')
        child_obj = obj
        parent_props = split_key[0:-1]
        for prop in parent_props:
            if prop not in child_obj:
                child_obj[prop] = {}
            child_obj = child_obj[prop]
        child_obj[split_key[-1]] = stix_value

    @staticmethod
    def _handle_cybox_key_def(key_to_add, observation, stix_value, obj_name_map, obj_name):
        """
        Handle the translation of the input property to its STIX CybOX property

        :param key_to_add: STIX property key derived from the mapping file
        :param observation: the the STIX observation currently being worked on
        :param stix_value: the STIX value translated from the input object 
        :param obj_name_map: the mapping of object name to actual object
        :param obj_name: the object name derived from the mapping file
        """
        obj_type, obj_prop = key_to_add.split('.', 1)
        objs_dir = observation['objects']
        if obj_name in obj_name_map:
            obj = objs_dir[obj_name_map[obj_name]]
        else:
            obj = {'type': obj_type}
            obj_dir_key = str(len(objs_dir))
            objs_dir[obj_dir_key] = obj
            if obj_name is not None:
                obj_name_map[obj_name] = obj_dir_key
        DataSourceObjToStixObj._add_property(obj, obj_prop, stix_value)

    @staticmethod
    def _valid_stix_value(props_map, key, stix_value):
        """
        Checks that the given STIX value is valid for this STIX property

        :param props_map: the map of STIX properties which contains validation attributes
        :param key: the STIX property name
        :param stix_value: the STIX value translated from the input object 
        :return: whether STIX value is valid for this STIX property
        :rtype: bool
        """
        if stix_value is None:
            return False
        elif key in props_map and 'valid_regex' in props_map[key]:
            pattern = re.compile(props_map[key]['valid_regex'])
            if not pattern.match(str(stix_value)):
                return False
        return True
    
    def transform(self, computer_obj):
        """
        Transforms the given object in to a STIX observation based on the mapping file and transform functions

        :param obj: the datasource object that is being converted to stix
        :return: the input object converted to stix valid json
        """

        object_map = {}
        final_obj = {}
        computer_id = computer_obj['computerID']
        computer_name = computer_obj['computerName']

        results = computer_obj['result']
        is_failure = computer_obj['isFailure']
        if is_failure == False:
            final_obj = DataSourceObjToStixObj.format_computer_obj(results)
        else:
            return 
        stix_type = 'observed-data'
        ds_map = self.ds_to_stix_map
        transformers = self.transformers
        observation = {
            'id': stix_type + '--' + str(uuid.uuid4()),
            'type': stix_type,
            "name": str(computer_id) + '-' + computer_name,
            'created_by_ref': self.identity_id,
            'objects': {}
        }

        # create normal type objects
        for ds_key in final_obj:
            if ds_key not in ds_map:
                print('{} is not found in map, skipping'.format(ds_key))
                continue
            ds_key_def_obj = self.ds_to_stix_map[ds_key]
            ds_key_def_list = ds_key_def_obj if isinstance(ds_key_def_obj, list) else [ds_key_def_obj]
            
            for ds_key_def in ds_key_def_list:
                if ds_key_def is None or 'key' not in ds_key_def:
                    logging.debug('{} is not valid (None, or missing key)'.format(ds_key_def))
                    continue
                
                key_to_add = ds_key_def['key']
                transformer = transformers[ds_key_def['transformer']] if 'transformer' in ds_key_def else None

                if ds_key_def.get('cybox', self.cybox_default):
                    object_name = ds_key_def.get('object')
                    if 'references' in ds_key_def:
                        stix_value = object_map[ds_key_def['references']]
                    else:
                        stix_value = DataSourceObjToStixObj._get_value(final_obj, ds_key, transformer)
                        if not DataSourceObjToStixObj._valid_stix_value(self.properties, key_to_add, stix_value):
                            continue
                    DataSourceObjToStixObj._handle_cybox_key_def(key_to_add, observation, stix_value, object_map, object_name)
                else:
                    stix_value = DataSourceObjToStixObj._get_value(final_obj, ds_key, transformer)
                    if not DataSourceObjToStixObj._valid_stix_value(self.properties, key_to_add, stix_value):
                        continue
                    DataSourceObjToStixObj._add_property(observation, key_to_add, stix_value)
        
        # Validate each STIX object
        if self.stix_validator:
            validated_result = validate_instance(observation)
            print_results(validated_result)
        
        return observation
    
    def format_computer_obj(computer_obj):
        # file, .X0-lock, sha256, 7236f966f07259a1de3ee0d48a3ef0ee47c4a551af7f0d76dcabbbb9d6e00940, sha1, 8b5e953be1db90172af66631132f6f27dda402d2, md5, e5307d27f0eb9a27af8597a1ddc51e89, /tmp/.X0-lock, 1541424894
        # process, systemd, 1, sha256, 9c74c625b2aba7a2e8d8a42e2e94715c355367f7cbfa9bd5404ba52b726792a6, sha1, 916933045c5c91ebcaa325e7f8302f3a732a0a3d, md5, 28a9beb86c4d4c31ba572805bea8494f, /usr/lib/systemd/systemd, 1541424881

        obj_list = computer_obj.split(',')
        formatted_obj = {}

        if computer_obj.startswith('process'):
            formatted_obj['start_time'] = obj_list[10].strip()
            formatted_obj['type'] = obj_list[0].strip()
            formatted_obj['process_name'] = obj_list[1].strip()
            formatted_obj['process_id'] = obj_list[2].strip()
            formatted_obj['sha256hash'] = obj_list[4].strip()
            formatted_obj['sha1hash'] = obj_list[6].strip()
            formatted_obj['md5hash'] = obj_list[8].strip()
            formatted_obj['file_path'] = obj_list[9].strip()
        elif computer_obj.startswith('file'):
            formatted_obj['type'] = obj_list[0].strip()
            formatted_obj['file_name'] = obj_list[1].strip()
            formatted_obj['sha256hash'] = obj_list[3].strip()
            formatted_obj['sha1hash'] = obj_list[5].strip()
            formatted_obj['md5hash'] = obj_list[7].strip()
            formatted_obj['file_path'] = obj_list[8].strip()
            formatted_obj['modified_time'] = obj_list[9].strip()
        else:
            print('Unknown result')

        return formatted_obj
