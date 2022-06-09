from yarl import URL

import base64
import sys
import urllib.request

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


def cat(u: str):
    url = URL(u)

    try:
        if url.scheme in ['http', 'https']:
            with urllib.request.urlopen(str(url)) as response:
                data = response.read()

            return data.decode()
        if url.scheme in ['ipfs'] or not url.scheme:
            # ipfs:// or raw cid/path

            if url.scheme and url.host:
                if url.path != '/':
                    path = url.host + url.path
                else:
                    path = url.host
            else:
                path = u

            data = ipfs_client.cat(path)
            return data.decode()
    except Exception as err:
        print(f'cat({u}) error: {err}', file=sys.stderr)

        raise Irate(err)


def cat64(url: str):
    data = cat(url)

    assert isinstance(data, str)
    return base64.b64encode(data.encode()).decode()


OmegaConf.register_new_resolver("include", yaml_include)
OmegaConf.register_new_resolver("cat", cat)
OmegaConf.register_new_resolver("cat64", cat64)
OmegaConf.register_new_resolver(
    "datenow_iso",
    lambda: datetime.now().isoformat(timespec='seconds', sep=' '))
