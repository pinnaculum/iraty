import base64
import sys
import urllib.request
import hashlib
import re
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
        elif url.scheme in ['ipfs', 'ipns'] or not url.scheme:
            # ipfs:// or ipns:// raw cid/path

            if url.scheme and url.hostname:
                path = f'/{url.scheme}/' + url.hostname
                if url.path != '/':
                    path += url.path
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

    p: ${cat:ipns://ipfs.io/index.html}
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


def unixfs_ls(path: str,
              regex: str,
              gwurl: str = 'https://dweb.link',
              limit: int = 0):
    """
    Generate a listing of a UnixFS directory, rendering it as an HTML
    list.

    :param path: IPFS object path to list
    :param regex: Regular expression to use to filter UnixFS entries with
    :param gwurl: URL of the IPFS HTTP gateway to generate links with
    :param limit: Maximum number of entries to list (0 means no limit)

    Examples:

    .: ${unixfs_ls:ipns://ipfs.io, .*}
    .: ${unixfs_ls:/ipns/dist.ipfs.io, .*, 'https://ipfs.io', 0}
    """

    node = {'ul': []}

    try:
        count = 0
        listing = ipfs_client.ls(path)

        for entry in listing['Objects'].pop()['Links']:
            if limit > 0 and count >= limit:
                break

            cid = entry['Hash']

            match = re.search(rf'{regex}', entry['Name'])
            if not match:
                continue

            if gwurl == 'ipfs' and 0:
                # TODO: handle CIDv0 conversion
                href = f'ipfs://{cid}'
            elif gwurl.startswith('https'):
                href = f'{gwurl}/ipfs/{cid}'
            elif not gwurl:
                href = f'https://dweb.link/ipfs/{cid}'

            node['ul'].append({
                'li': {
                    'a': {
                        '_href': href,
                        '_': entry['Name']
                    }
                }
            })
            count += 1
    except Exception as err:
        print(f'unixfs_ls({path}) error: {err}', file=sys.stderr)

    return node


OmegaConf.register_new_resolver("block", block)
OmegaConf.register_new_resolver("csum_hex", csum_hex)
OmegaConf.register_new_resolver("include", include)
OmegaConf.register_new_resolver("unixfs_ls", unixfs_ls)
OmegaConf.register_new_resolver("cat", cat)
OmegaConf.register_new_resolver("cat64", cat64)
OmegaConf.register_new_resolver(
    "dtnow_iso",
    lambda: datetime.now().isoformat(timespec='seconds', sep=' '))
