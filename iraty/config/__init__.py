import editor
import sys
from pathlib import Path

from omegaconf import OmegaConf


default_lint_config = '''
---

yaml-files:
  - '*.yaml'
  - '*.yml'

rules:
  empty-lines: disable
  empty-values: disable
  indentation: enable
  key-duplicates: enable
  key-ordering: disable
  line-length: disable
  new-line-at-end-of-file: disable
  new-lines: enable
  octal-values: disable
  quoted-strings: disable
  trailing-spaces: enable
  truthy:
    level: warning
'''


ipfs_nodecfg_yaml_template = '''
# IPFS node API multiaddr
ipfs_api_maddr: '/dns/localhost/tcp/5001/http'

# Default pinning service name (string)
ipfs_rps_default: null

# Configure a remote pinning service
ipfs_rps_cfg:
  # service name
  pinata:
    # Endpoint URL
    endpoint: https://api.pinata.cloud/psa

    # RPS secret
    key: null
'''


def node_get_config(nodes_config_path: Path, name: str):
    ncp = nodes_config_path.joinpath(f'{name}.yaml')

    try:
        return ncp, OmegaConf.load(ncp)
    except Exception:
        return ncp, None


def node_configure_default(config_path: Path, nodes_config_path: Path):
    """
    Configure the default node ("local") if it doesn't exist yet
    """
    ncp = nodes_config_path.joinpath('local.yaml')

    if not ncp.is_file():
        with open(ncp, 'wt') as fd:
            fd.write(ipfs_nodecfg_yaml_template)


def node_configure(args, config_path: Path, nodes_config_path: Path):
    template = ipfs_nodecfg_yaml_template

    if len(args.input) != 1:
        print('Please specify a node name', file=sys.stderr)
        return None

    name = args.input[0]

    ncp, saved = node_get_config(nodes_config_path, name)
    try:
        saved = OmegaConf.load(ncp)
    except Exception:
        saved = None

    if saved:
        yaml = OmegaConf.to_yaml(saved)
        cc = editor.edit(contents=str(yaml))
    else:
        cc = editor.edit(contents=template)

    try:
        cfg = OmegaConf.create(cc.decode())

        with open(ncp, 'wt') as fd:
            OmegaConf.save(cfg, fd)

        return cfg
    except Exception as err:
        raise err
