import base64

from datetime import datetime

from omegaconf import OmegaConf


# Global
ipfs_client = None


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


OmegaConf.register_new_resolver("cat", ipfs_cat)
OmegaConf.register_new_resolver("ipfs_cat", ipfs_cat)
OmegaConf.register_new_resolver("cat64", ipfs_cat64)
OmegaConf.register_new_resolver("ipfs_cat64", ipfs_cat64)
OmegaConf.register_new_resolver("datenow_iso",
                                lambda: datetime.now().isoformat())
