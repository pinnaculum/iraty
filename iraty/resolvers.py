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


def include(path: str):
    """
    Include another YAML file and render it.

    :param path: The path to the YAML file
    :type path: str

    Examples:

    .: ${include:.banner.yml}
    .: ${include:dir1/.article.yml}
    """

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
    """
    Returns the contents (as string) of the requested resource.

    :param url: The resource URL (http, https or ipfs)
    :type url: str
    :rtype: str

    Examples:

    p: ${cat:ipns://ipfs.io}
    """

    data = cat_raw(url)

    assert isinstance(data, bytes)
    return data.decode()


def cat64(url: str):
    """
    Returns the base64-encoded content (as string) of the requested resource.

    :param url: The resource URL (http, https or ipfs)
    :type url: str
    :rtype: str

    Examples:

    span: ${cat:bafkreihszin3nr7ja7ig3l7enb7fph6oo2zx4tutw5qfaiw2kltmzqtp2i}
    p: ${cat64:ipns://ipfs.io}
    """

    data = cat_raw(url)

    assert isinstance(data, bytes)
    return base64.b64encode(data).decode()


def csum_hex(algo: str, url: str):
    """
    Returns the hexadecimal checksum of a remote or local file for the
    specified hashing algorithm.

    :param algo: The hashing algorithm
    :type algo: str
    :param url: The resource URL (http, https or ipfs)
    :type url: str

    Example:

    span: ${csum_hex:sha512,bafkreihszin3nr7ja7ig3l7enb7fph6oo2zx4tutw5qfaiw2kltmzqtp2i}
    """

    if algo not in hashlib.algorithms_guaranteed:
        raise Irate(f'Algorithm {algo} is not supported')

    h = hashlib.new(algo)

    data = cat_raw(url)

    if data:
        h.update(data)
        return h.hexdigest()
    else:
        raise Irate(f'Empty object: {url}')


def block(block_name: str):
    """
    Create a block in a layout

    :param block_name: The name of the block to create
    :type block_name: str

    Example:

    ${block:rightdiv}
    ${block:top}
    """
    return OmegaConf.create({f'block_{block_name}': None})


OmegaConf.register_new_resolver("block", block)
OmegaConf.register_new_resolver("csum_hex", csum_hex)
OmegaConf.register_new_resolver("include", include)
OmegaConf.register_new_resolver("cat", cat)
OmegaConf.register_new_resolver("cat64", cat64)
OmegaConf.register_new_resolver(
    "dtnow_iso",
    lambda: datetime.now().isoformat(timespec='seconds', sep=' '))
