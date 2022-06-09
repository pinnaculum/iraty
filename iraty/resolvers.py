import base64
import sys
import urllib.request
import hashlib
from urllib.parse import urlparse

from datetime import datetime

from omegaconf import OmegaConf


# Global
ipfs_client = None
root_path = None
search_paths = None


class Irate(Exception):
    pass


def yaml_include(path: str):
    try:
        assert root_path is not None

        fp = root_path.joinpath(path)

        with open(fp, 'rt') as fd:
            yam = OmegaConf.load(fd)

        return yam
    except Exception as err:
        print(err, file=sys.stderr)


def cat_raw(u: str):
    try:
        url = urlparse(u)

        if url.scheme in ['http', 'https']:
            with urllib.request.urlopen(u) as response:
                data = response.read()

            return data
        if url.scheme in ['ipfs'] or not url.scheme:
            # ipfs:// or raw cid/path

            if url.scheme and url.hostname:
                if url.path != '/':
                    path = url.hostname + url.path
                else:
                    path = url.hostname
            else:
                path = u

            data = ipfs_client.cat(path)
            return data
    except Exception as err:
        print(f'cat({u}) error: {err}', file=sys.stderr)

        raise Irate(err)


def cat(url: str):
    data = cat_raw(url)

    assert isinstance(data, bytes)
    return data.decode()


def cat64(url: str):
    data = cat_raw(url)

    assert isinstance(data, bytes)
    return base64.b64encode(data).decode()


def checksum_hex(algo: str, ref: str):
    if algo not in hashlib.algorithms_guaranteed:
        raise Irate(f'Algorithm {algo} is not supported')

    h = hashlib.new(algo)

    data = cat_raw(ref)

    if data:
        h.update(data)
        return h.hexdigest()
    else:
        raise Irate(f'Empty object: {ref}')


OmegaConf.register_new_resolver("csum_hex", checksum_hex)
OmegaConf.register_new_resolver("include", yaml_include)
OmegaConf.register_new_resolver("cat", cat)
OmegaConf.register_new_resolver("cat64", cat64)
OmegaConf.register_new_resolver(
    "datenow_iso",
    lambda: datetime.now().isoformat(timespec='seconds', sep=' '))
