from ..base.base_ping import BasePing
import json


class SplunkPing(BasePing):
    def __init__(self, api_client):
        self.api_client = api_client
    
    def ping(self):
        try:
            response = self.api_client.ping_box()
            response_code = response.code

            response_json = response.read()
           
            return_obj = dict()
            return_obj['success'] = False

            if len(response_json) > 0 and response_code == 200:
                return_obj['success'] = True
            else:
                return_obj['error'] = response_json['messages']

            return return_obj

        except Exception as err:
            return_obj = dict()
            return_obj['success'] = False
            return_obj['error'] = 'error when pinging data source: {}'.format(err)
            return return_obj
