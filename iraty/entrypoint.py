import sys
import io
import argparse
import markdown
import traceback
from pathlib import Path

from domonic.dom import document
from domonic.html import html
from domonic.html import render
from omegaconf import OmegaConf

try:
    from html5print import HTMLBeautifier
except ImportError:
    have_beautifier = False
else:
    have_beautifier = True

import ipfshttpclient
from ipfshttpclient import client

from . import resolvers


def assert_v(version: str, minimum: str = '0.4.23',
             maximum: str = '0.15.0') -> None:
    # Don't really care which version you use
    pass


client.assert_version = assert_v


def convert(node, dom, parent=None):
    pn = parent if parent is not None else dom

    if isinstance(node, dict):
        for elem, n in node.items():
            if elem.startswith('_'):
                # Attribute
                pn.setAttribute(elem.replace('_', ''), n)
            else:
                tag = document.createElement(elem)

                if isinstance(n, str) and 0:
                    htmlized = markdown.markdown(n)
                    tag.innerText(htmlized)

                pn.appendChild(tag)

                convert(node[elem], dom, parent=tag)
    elif isinstance(node, list):
        for n in node:
            tag = document.createElement('span')
            pn.appendChild(tag)
            convert(n, dom, parent=tag)
    elif isinstance(node, str):
        tag = document.createElement('span')
        htmlized = markdown.markdown(node)
        tag.innerText(htmlized)
        pn.appendChild(tag)


def iraty(args):
    if len(args.input) != 1:
        print('Invalid input arguments', file=sys.stderr)
        sys.exit(1)

    filein = args.input[0]

    try:
        iclient = ipfshttpclient.connect(args.ipfsmaddr)
    except Exception as err:
        # Should be fatal ?
        print(f'IPFS connection Error: {err}', file=sys.stderr)
    else:
        # Set global client
        resolvers.ipfs_client = iclient

    path = Path(filein)

    if not path.is_file():
        print(f'File {path} does not exist', file=sys.stderr)
        sys.exit(1)

    dom = html()
    output = io.BytesIO()

    try:
        with open(str(path), 'rt') as fd:
            foc = OmegaConf.load(fd)

            convert(
                OmegaConf.to_container(foc, resolve=True),
                dom
            )

            if have_beautifier:
                out = HTMLBeautifier.beautify(render(dom),
                                              int(args.htmlindent))
                output.write(out.encode())
            else:
                output.write(f'{dom}'.encode())

            output.seek(0, 0)

            if args.ipfsout:
                try:
                    entry = iclient.add(output, cid_version=1)
                    print(entry['Hash'])
                except Exception as err:
                    print(f'IPFS Error: {err}', file=sys.stderr)
            else:
                print(output.getvalue().decode())
    except Exception:
        traceback.print_exc()
        sys.exit(2)


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--ipfs-maddr',
        dest='ipfsmaddr',
        default='/dns/localhost/tcp/5001/http',
        help='IPFS daemon multiaddr')
    parser.add_argument(
        '--html-indent',
        dest='htmlindent',
        default=4,
        help='HTML indentation space count')
    parser.add_argument(
        '--ipfs',
        dest='ipfsout',
        action='store_true',
        default=False,
        help='Store HTML output to IPFS')

    parser.add_argument(nargs=1, dest='input')

    return iraty(parser.parse_args())
