import requests
import base64
import sys

from datetime import datetime

from omegaconf import OmegaConf


# Global
ipfs_client = None


def yaml_get(yaml_url: str):
    try:
        data = requests.request('GET', yaml_url)

        if data.status_code != 200:
            print(f'GET {yaml_url} failed', file=sys.stderr)

            raise Exception(f'{yaml_url}: HTTP code: {data.status_code}')

        if data.content:
            obj = OmegaConf.create(data.content.decode())

            return OmegaConf.to_container(obj, resolve=True)
    except Exception as err:
        print(f'Failed to read: {yaml_url}: {err}', file=sys.stderr)


def ipfs_cat(path: str):
    try:
        data = ipfs_client.cat(path)
        return data.decode()
    except Exception:
        return None


def ipfs_cat64(path: str):
    try:
        data = ipfs_client.cat(path)
        return base64.b64encode(data).decode()
    except Exception:
        return None


OmegaConf.register_new_resolver("yaml_get", yaml_get)
OmegaConf.register_new_resolver("cat", ipfs_cat)
OmegaConf.register_new_resolver("ipfs_cat", ipfs_cat)
OmegaConf.register_new_resolver("cat64", ipfs_cat64)
OmegaConf.register_new_resolver("ipfs_cat64", ipfs_cat64)
OmegaConf.register_new_resolver("datenow_iso",
                                lambda: datetime.now().isoformat())
