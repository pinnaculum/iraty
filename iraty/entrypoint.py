import argparse

from .iraty import iraty


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--ipfs-maddr',
        dest='ipfsmaddr',
        default=None,
        help='Use a specific IPFS daemon multiaddr')

    parser.add_argument(
        '--node',
        '--ipfs-node',
        dest='ipfs_node',
        default='local',
        help='Configured IPFS node name to use (default: "local")')

    parser.add_argument(
        '--html-indent',
        dest='htmlindent',
        default=4,
        help='HTML indentation space count')

    parser.add_argument(
        '-i',
        '--ipfs',
        dest='ipfsout',
        action='store_true',
        default=False,
        help='Store HTML output to IPFS')

    parser.add_argument(
        '-s',
        '--serve',
        dest='httpserve',
        action='store_true',
        default=False,
        help='Serve website via HTTP')

    parser.add_argument(
        '--port',
        '--serve-port',
        dest='httpport',
        type=int,
        default=8000,
        help='TCP port for the HTTP service')

    parser.add_argument(
        '-o',
        '--out',
        dest='outdir',
        default='public',
        help='Output directory path (default: "public")')

    parser.add_argument(
        '--purge',
        dest='purge',
        action='store_true',
        default=True,
        help='Purge output directory before rendering')

    parser.add_argument(
        '-t',
        '--theme',
        dest='theme',
        default='mercury',
        help='Theme to use')

    parser.add_argument(
        '-r',
        dest='restore_config',
        action='store_true',
        default=False,
        help='Restore last saved site configuration (.iraty.yaml)')

    parser.add_argument(
        '--pr',
        '--pin-remote',
        '--pin-to-remote',
        dest='pintoremote',
        action='store_true',
        default=False,
        help='Pin webpage/website to the IPFS remote pinning service')

    parser.add_argument(
        '--rps',
        dest='rps_name',
        default=None,
        help='Use a specific remote pinning service (RPS)')

    parser.add_argument(
        nargs=1, default='run', dest='cmd',
        help='Command: run, serve, list-resolvers, list-themes, node-config'
    )
    parser.add_argument(nargs='*', dest='input')

    return iraty(parser.parse_args())
