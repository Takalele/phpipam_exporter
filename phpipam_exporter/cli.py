"""Console script for phpipam_exporter."""
import glob
import logging
import os
import subprocess
import sys
from ipaddress import IPv4Address

from jinja2 import Environment, FileSystemLoader, select_autoescape

import click

from phpipam_exporter.libs.ipam import IPAM
from phpipam_exporter.libs.functions import dhcp_option_names_to_int

logger = logging.getLogger('IPAM')

BASE_DIR = f'{os.path.dirname(os.path.realpath(__file__))}/'

formats = [os.path.basename(it).replace('.j2', '')
           for it in glob.glob(f'{BASE_DIR}templates/*.j2')]


@click.command()
@click.option('--host', envvar='PHPIPAM_HOST', required=True,
              help="phpipam API entrypoint. "
                   "(e.g. https://<fqdn>/api/<api_id>/)")
@click.option('--token', envvar='PHPIPAM_TOKEN', required=True,
              help="phpipam API token.")
@click.option('--custom-template', 'custom_template',
              envvar='PHPIPAM_CUSTOM_TEMPLATE',
              help="Custom Jinja template file.", type=click.Path())
@click.option('--output', '-o', 'output_file', envvar='PHPIPAM_OUTPUT',
              help="Output file.", type=click.Path())
@click.option('--on-change-action', 'on_change_action',
              envvar='PHPIPAM_ON_CHANGE_ACTION',
              help="This script is fired when output file is changed.")
@click.option("--secure/--insecure", "verify",
              envvar="PHPIPAM_VERIFY",
              help="Configure TLS certificate verification.",
              is_flag=True,
)
def main(host, token, custom_template, output_file,
         on_change_action,verify):
    """
    Export ip addresses from phpipam to many formats.
    """
    template_dir = f"{BASE_DIR}templates"
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape()
    )
    try:
        get_all_devices = IPAM(host, token, verify).get_devices()
        for device in get_all_devices:
            data = ""
            device_name = device['hostname']
            output_file = device_name + '.' + 'conf'
            device_id = device['id']
            format = device['custom_fields']['custom_DHCP_FORMAT']
            if not format:
                format = 'json'
            template_file = f"{format}.j2"
            if custom_template:
                template_dir = os.path.dirname(custom_template)
                template_file = os.path.basename(custom_template)
            devices_subnets = IPAM(host, token, verify).get_device_subnets(device_id, device_name)
            if devices_subnets is not None:
                devices_subnets_count = 0
                for subnets in devices_subnets:
                    try:
                        subnet_id = subnets['id']
                        subnetinfo = IPAM(host, token, verify).get_subnet_info(subnet_id)
                        for subnet in subnetinfo:
                            if subnet['data']['custom_fields']['custom_DHCP'] == 1:
                                if subnet['data']['vlanId'] is not None:
                                    vlan_id = subnet['data']['vlanId']
                                    subnet_vlan_info = IPAM(host, token, verify).get_vlan_info(vlan_id)
                                    for entry in subnet_vlan_info:
                                        subnet_name = entry['data']['name']
                                elif subnet['data']['description'] is not None:
                                    subnet_name = subnet['data']['description']
                                else:
                                    devices_subnets_count = devices_subnets_count +1
                                    subnet_name = "Default-" + str(devices_subnets_count)
                                if subnet['data']['custom_fields']['custom_DHCP_RANGE_START'] is not None and subnet['data']['custom_fields']['custom_DHCP_RANGE_END'] is not None:
                                    subnet_dhcp_range_start = subnet['data']['custom_fields']['custom_DHCP_RANGE_START']
                                    subnet_dhcp_range_end = subnet['data']['custom_fields']['custom_DHCP_RANGE_END']
                                elif subnet['data']['custom_fields']['custom_DHCP_RANGE_START'] is not None and subnet['data']['custom_fields']['custom_DHCP_RANGE_END'] is None:
                                    subnet_dhcp_range_start = subnet['data']['custom_fields']['custom_DHCP_RANGE_START']
                                    subnet_dhcp_range_end = str(IPv4Address(subnet['data']['calculation']['Max host IP'] ))
                                elif subnet['data']['custom_fields']['custom_DHCP_RANGE_START'] is None and subnet['data']['custom_fields']['custom_DHCP_RANGE_END'] is not None:
                                    subnet_dhcp_range_start = str(IPv4Address(subnet['data']['calculation']['Min host IP'] ) + 1)
                                    subnet_dhcp_range_end = subnet['data']['custom_fields']['custom_DHCP_RANGE_END']
                                else:
                                    subnet_dhcp_range_start = str(IPv4Address(subnet['data']['calculation']['Min host IP'] ) + 1)
                                    subnet_dhcp_range_end = str(IPv4Address(subnet['data']['calculation']['Max host IP'] ))
                                subnet_dhcp_confvar_prefix = 'custom_DHCP_CONF_VAR_'
                                subnet_dhcp_confvar = {key: value for key, value in subnet['data']['custom_fields'].items() if key.startswith(subnet_dhcp_confvar_prefix) and value is not None}
                                subnet_dhcp_option_prefix = 'custom_DHCP_OPTION_'
                                subnet_dhcp_option = {
                                    key: dhcp_option_names_to_int(value)
                                    for key, value in subnet['data']['custom_fields'].items()
                                    if key.startswith(subnet_dhcp_option_prefix) and value is not None
                                }       
                                if "gateway" in subnet['data']:
                                    subnet_gw = subnet['data']['gateway']['ip_addr']
                                else:
                                    subnet_gw = subnet['data']['calculation']['Min host IP']
                                if "calculation" in subnet['data']:
                                    subnet_mask = subnet['data']['calculation']['Subnet netmask']
                                    subnet_network = subnet['data']['calculation']['Network'] + "/" + subnet['data']['calculation']['Subnet bitmask']
                                if "nameservers" in subnet['data']:
                                    logger.debug(f'Name Server found in Subnet "{subnet}".')
                                    subnet_nameservers = subnet['data']['nameservers']['namesrv1']
                                else:
                                    logger.debug(f'Name Server not found in Subnet "{subnet}".')
                                    if "gateway" in subnet['data']:
                                        subnet_nameservers = subnet['data']['gateway']['ip_addr']
                                        logger.debug(f'Name Server not found in Subnet "{subnet}". defaulting to Gateway IP as Name Server.')
                                    else:
                                        logger.debug(f'Name Server not found in Subnet "{subnet}". defaulting to Google and Cloudflare for DNS')
                                        subnet_nameservers ='8.8.8.8;1.1.1.1'
                                try:
                                    addresses = IPAM(host, token, verify).get_addresses(subnet['data']['id'])
                                except:
                                    addresses=[]
                                    pass
                                subnet_address_dhcp_option = {}
                                for address in addresses:
                                    if "custom_fields" in address:
                                        subnet_address_dhcp_option[address['id']] = {}
                                        subnet_address_dhcp_option[address['id']] = {
                                            key: dhcp_option_names_to_int(value)
                                            for key, value in address['custom_fields'].items()
                                            if key.startswith(subnet_dhcp_option_prefix) and value is not None
                                        }    
                                template = env.get_template(template_file)
                                data += "\n"+template.render(device_name=device_name,subnet_name=subnet_name,subnet_dhcp_range_start=subnet_dhcp_range_start,subnet_dhcp_range_end=subnet_dhcp_range_end,subnet_dhcp_option=subnet_dhcp_option,subnet_dhcp_confvar=subnet_dhcp_confvar,subnet_mask=subnet_mask,subnet_gw=subnet_gw,subnet_nameservers=subnet_nameservers,subnet_network=subnet_network,addresses=addresses,subnet_address_dhcp_option=subnet_address_dhcp_option)
                                
                    except:
                        logger.debug(f'Error with id "{subnet_id}".')

            overwrite = True
            if data:
                if on_change_action and os.path.exists(output_file):
                    with open(output_file, 'r') as fd_org:
                        original = fd_org.read()
                    overwrite = original != data
                if overwrite:
                    with open(output_file, 'w+') as fd_out:
                        fd_out.write(data)
                    if on_change_action:
                        subprocess.run(on_change_action, check=True, shell=True)

    except Exception as ex:
        logging.error(ex, exc_info=ex)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
