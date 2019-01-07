import logging
import requests
from typing import List
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from transmissionrpc import TransmissionError
from nefarious.models import NefariousSettings
from nefarious.tmdb import get_tmdb_client
from nefarious.transmission import get_transmission_client


def is_magnet_url(url: str) -> bool:
    return url.startswith('magnet:')


def swap_jackett_host(url: str, nefarious_settings: NefariousSettings) -> str:
    parsed = urlparse(url)
    return '{}://{}:{}{}?{}'.format(
        parsed.scheme, nefarious_settings.jackett_host, nefarious_settings.jackett_port,
        parsed.path, parsed.query,
    )


def trace_torrent_url(url: str) -> str:

    if is_magnet_url(url):
        return url

    # validate torrent file response
    response = requests.get(url, allow_redirects=False, timeout=30)
    if not response.ok:
        raise Exception(response.content)
    # redirected to a magnet link so use that instead
    elif response.is_redirect and is_magnet_url(response.headers['Location']):
        return response.headers['Location']

    return url


def verify_settings_tmdb(nefarious_settings: NefariousSettings):
    # verify tmdb configuration settings
    try:
        tmdb_client = get_tmdb_client(nefarious_settings)
        configuration = tmdb_client.Configuration()
        configuration.info()
    except Exception as e:
        logging.error(str(e))
        raise Exception('Could not fetch TMDB configuration')


def verify_settings_transmission(nefarious_settings: NefariousSettings):
    # verify transmission
    try:
        get_transmission_client(nefarious_settings)
    except TransmissionError:
        raise Exception('Could not connect to transmission')


def verify_settings_jackett(nefarious_settings: NefariousSettings):
    """
    A special "all" indexer is available at /api/v2.0/indexers/all/results/torznab/api. It will query all configured indexers and return the combined results.
    NOTE: /api/v2.0/indexers/all/results  will return json results vs torznab's xml response
    """
    try:
        # make an unspecified query to the "all" indexer results endpoint and see if it's successful
        response = requests.get('http://{}:{}/api/v2.0/indexers/all/results'.format(
            nefarious_settings.jackett_host, nefarious_settings.jackett_port), params={'apikey': nefarious_settings.jackett_token}, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(str(e))
        raise Exception('Could not connect to jackett')


def fetch_jackett_indexers(nefarious_settings: NefariousSettings) -> List[str]:
    """
    To get all Jackett indexers including their capabilities you can use t=indexers on the all indexer.
    To get only configured/unconfigured indexers you can also add configured=true/false as query parameter.
    """
    response = requests.get('http://{}:{}/api/v2.0/indexers/all/results/torznab/api'.format(
        nefarious_settings.jackett_host, nefarious_settings.jackett_port),
        params={
            'apikey': nefarious_settings.jackett_token,
            't': 'indexers',
            'configured': 'true',
        }, timeout=60)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    indexers = []
    for child in root:
        indexers.append(child.attrib['id'])
    return indexers

