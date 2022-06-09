import sys
import os
import io
import argparse
import tempfile
import markdown
import traceback
import shutil
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
from ipfshttpclient.exceptions import ErrorResponse

from . import resolvers


def assert_v(version: str, minimum: str = '0.4.23',
             maximum: str = '0.15.0') -> None:
    # Ignore go-ipfs version number (we only use a small subset of the API)
    pass


client.assert_version = assert_v


def handle_textnode(pn, text: str):
    if pn.tagName in ['p', 'span']:
        pn.innerText(markdown.markdown(text))
    else:
        pn.innerText(text)


def convert(node, dom, parent=None):
    pn = parent if parent is not None else dom

    if isinstance(node, dict):
        for elem, n in node.items():
            if len(elem) > 1 and elem.startswith('_'):
                # Attribute
                pn.setAttribute(elem.replace('_', ''), n)
            elif elem in ['raw', '.']:
                # In-place
                convert(n, dom, parent=pn)
                continue
            elif elem == '_' and isinstance(n, str):
                # Tag text contents
                handle_textnode(pn, n)
            else:
                # Create HTML tag
                tag = document.createElement(elem)
                pn.appendChild(tag)

                convert(node[elem], dom, parent=tag)
    elif isinstance(node, list):
        [convert(subn, dom, parent=pn) for subn in node]
    elif isinstance(node, str):
        handle_textnode(pn, node)


class Iraty:
    def __init__(self, ipfs_client, args):
        self.iclient = ipfs_client
        self.args = args

    def ipfs_add(self, src):
        try:
            ret = self.iclient.add(src, cid_version=1,
                                   recursive=True)
            if isinstance(ret, list):
                entry = ret[-1]
            else:
                entry = ret

            return entry['Hash']
        except Exception as err:
            print(f'IPFS Error: {err}', file=sys.stderr)

    def ipfs_pinremote(self, service, cid):
        try:
            resp = self.iclient.pinremote.add(service, cid)
            assert resp['Status'] == 'pinned'
        except ErrorResponse as err:
            print(f'Pin to remote error: {err}', file=sys.stderr)
            return False
        except Exception as err:
            print(f'Unknown Error: {err}', file=sys.stderr)
            return False
        else:
            return True

    def output_dom(self, dom, dest: Path = None, fd=None):
        if dest:
            output = open(str(dest), 'wb')
        else:
            output = fd if fd else io.BytesIO()
        try:
            if have_beautifier and 0:
                out = HTMLBeautifier.beautify(render(dom),
                                              int(self.args.htmlindent))
                if output is sys.stdout:
                    output.write(out)
                else:
                    output.write(out.encode())
            else:
                if output is sys.stdout:
                    output.write(f'{dom}')
                else:
                    output.write(f'{dom}'.encode())

            if output is not sys.stdout:
                output.seek(0, 0)
        except Exception:
            traceback.print_exc()
        else:
            return output

    def process_file(self, path: Path, output=False):
        dom = html()
        try:
            with open(str(path), 'rt') as fd:
                foc = OmegaConf.load(fd)

                convert(
                    OmegaConf.to_container(foc, resolve=True),
                    dom
                )
        except Exception:
            traceback.print_exc()
            return None

        if output:
            if self.args.ipfsout:
                out = self.output_dom(dom)
                cid = self.ipfs_add(out)

                if cid:
                    if self.args.pintoremote:
                        # Pin to remote service
                        self.ipfs_pinremote(self.args.pintoremote, cid)

                    print(cid, file=sys.stdout)
            else:
                self.output_dom(dom, fd=sys.stdout)

        return dom

    def process_directory(self, path: Path):
        outd = tempfile.mkdtemp()
        try:
            for root, dirs, files in os.walk(str(path)):
                rr = root.replace(str(path), '').lstrip(os.sep)

                for file in files:
                    fp = Path(root).joinpath(file)
                    ddest = Path(outd).joinpath(rr)
                    ddest.mkdir(parents=True, exist_ok=True)

                    if fp.name.startswith('.'):
                        # Ignore dot files (reserved)
                        continue

                    if fp.name.endswith('.yaml') or fp.name.endswith('.yml'):
                        fname = file.replace('.yaml', '.html').replace(
                            '.yml', '.html')
                        dest = ddest.joinpath(fname)
                        dom = self.process_file(fp)

                        if dom:
                            self.output_dom(dom, dest=dest)
                    else:
                        # Copy other files
                        shutil.copy(fp, str(ddest))
        except Exception:
            traceback.print_exc()
        else:
            if self.args.ipfsout:
                cid = self.ipfs_add(outd)

                if cid:
                    if self.args.pintoremote:
                        # Pin to remote service
                        if self.ipfs_pinremote(self.args.pintoremote, cid):
                            print(cid, file=sys.stdout)
                    else:
                        print(cid, file=sys.stdout)
            else:
                print(outd, file=sys.stdout)


def iraty(args):
    if len(args.input) != 1:
        print('Invalid input arguments', file=sys.stderr)
        sys.exit(1)

    filein = args.input[0]

    try:
        iclient = ipfshttpclient.connect(args.ipfsmaddr)
    except Exception as err:
        # Should be fatal ?
        iclient = None
        print(f'IPFS connection Error: {err}', file=sys.stderr)
    else:
        # Set global client
        resolvers.ipfs_client = iclient

    ira = Iraty(iclient, args)
    path = Path(filein)

    if not path.exists():
        print(f'{path} does not exist', file=sys.stderr)
        sys.exit(1)

    if path.is_file():
        resolvers.root_path = path.parent
        ira.process_file(path, output=True)
    elif path.is_dir():
        resolvers.root_path = path
        ira.process_directory(path)


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
        '-i',
        '--ipfs',
        dest='ipfsout',
        action='store_true',
        default=False,
        help='Store HTML output to IPFS')

    parser.add_argument(
        '-pr',
        '--pin-remote',
        '--pin-to-remote',
        dest='pintoremote',
        default=None,
        help='Pin webpage/website to a remote IPFS pinning service')

    parser.add_argument(nargs=1, dest='input')

    return iraty(parser.parse_args())
