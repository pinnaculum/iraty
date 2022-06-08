import base64
import sys

from datetime import datetime

from omegaconf import OmegaConf


# Global
ipfs_client = None
root_path = None
search_paths = None


def yaml_include(path: str):
    try:
        assert root_path is not None

        fp = root_path.joinpath(path)

        with open(fp, 'rt') as fd:
            yam = OmegaConf.load(fd)

        return yam
    except Exception as err:
        print(err, file=sys.stderr)


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


OmegaConf.register_new_resolver("include", yaml_include)
OmegaConf.register_new_resolver("cat", ipfs_cat)
OmegaConf.register_new_resolver("ipfs_cat", ipfs_cat)
OmegaConf.register_new_resolver("cat64", ipfs_cat64)
OmegaConf.register_new_resolver("ipfs_cat64", ipfs_cat64)
OmegaConf.register_new_resolver(
    "datenow_iso",
    lambda: datetime.now().isoformat(timespec='seconds', sep=' '))
