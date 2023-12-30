"""Main module."""
import logging
from .api import Api

logger = logging.getLogger('IPAM')


class IPAM:

    def __init__(self, uri: str, token: str, verify: bool):
        self.api = Api(uri, headers={'token': token}, verify=verify)

    def get_subnet(self, name: str):
        logger.debug(f'Get subnet "{name}".')
        res = self.api.get(f'/subnets/search/{name}/', timeout=10)
        logger.debug(f'Response: {res}')
        if res:
            return res.pop(0)
        return res
    
    def get_subnet_info(self, subnet_id: int):
        _info = []
        logger.debug(f'Get information on Subnet"{subnet_id}".')
        _info.append({
            'subnet_id': subnet_id,
            'data': self.api.get(f'/subnets/{subnet_id}/', timeout=20)
        })
        return _info

    def get_addresses(self, subnet_id: int):
        _addresses = []
        logger.debug(f'Get addresses for subnet "{subnet_id}".')
        _addresses += self.api.get(f'/subnets/{subnet_id}/addresses/',
                                       timeout=20)
        return _addresses
    
    def get_devices(self):
        _devices = []
        logger.debug(f'Get Devices.')
        _devices += self.api.get(f'/devices/',
                                       timeout=20)
        return _devices

    def get_device_subnets(self, device_id: int, device_name: str):
        _info = []
        logger.debug(f'Get subnets for device_id "{device_name}".')
        try:
            _info += self.api.get(f'/devices/{device_id}/subnets/',
                                        timeout=20)
            return _info
        except:
            logger.debug(f'No Supnet found for device "{device_name}".')
            return None
        

    def get_device_info(self, device_id: int):
        _info = []
        logger.debug(f'Get Device Info "{device_id}".')
        _info.append({
                'device_id': device_id,
                'data': self.api.get(f'/devices/{device_id}/', timeout=20)
            })
        return _info

    def get_device_name(self, device_id: int):
        _info = []
        logger.debug(f'Get name for Device "{device_id}".')
        _info += self.api.get(f'/devices/{device_id}/addresses/',
                                       timeout=20)
        return _info
    
    def get_vlan_info(self, vlan_id: int):
        _info = []
        logger.debug(f'Get info about vlan "{vlan_id}".')
        _info.append({
                'vlan_id': vlan_id,
                'data': self.api.get(f'/vlan/{vlan_id}/', timeout=20)
            })
        return _info