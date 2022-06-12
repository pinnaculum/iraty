import sys
import os
import os.path
import io
import inspect
import markdown
import traceback
import shutil
import functools
import http.server
import socketserver
import pkg_resources
import subprocess
from pathlib import Path

from domonic.dom import document
from domonic.html import html
from domonic.html import render
from omegaconf import OmegaConf
from omegaconf.basecontainer import BaseContainer
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import node_get_config
from .config import node_configure
from .config import node_configure_default

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
from . import appdirs


def is_str(obj):
    return isinstance(obj, str)


def assert_v(version: str, minimum: str = '0.4.23',
             maximum: str = '0.15.0') -> None:
    # Ignore go-ipfs version number (we only use a small subset of the API)
    pass


client.assert_version = assert_v


def http_serve(directory: Path, port=8000):
    """
    Serve via HTTP the specified directory on the given TCP port
    """

    Handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(directory)
    )

    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f'Serving via HTTP at: http://localhost:{port}', file=sys.stdout)

        httpd.serve_forever()


def handle_textnode(pn, text: str):
    if pn.tagName in ['p', 'span']:
        pn.innerText(markdown.markdown(text))
    else:
        pn.innerText(text)


jenv = Environment(autoescape=select_autoescape())


def convert(node, dom, parent=None):
    pn = parent if parent is not None else dom

    if isinstance(node, dict):
        for elem, n in node.items():
            if len(elem) > 1 and elem.startswith('_'):
                # Attribute
                pn.setAttribute(elem.replace('_', ''), n)
            elif elem in ['.', '..']:
                # in situ
                convert(n, dom, parent=pn)
                continue
            elif elem == '_' and is_str(n):
                # Tag text contents
                handle_textnode(pn, n)
            elif elem == 'jinja':
                args = {}

                if is_str(n):
                    tmpl = jenv.from_string(n)
                elif isinstance(n, dict):
                    args = n.get('with', {})
                    tpath = n.get('from')
                    template = n.get('template')

                    if is_str(tpath):
                        tmpl = jenv.get_template(tpath)
                    elif is_str(template):
                        tmpl = jenv.from_string(template)

                if tmpl:
                    pn.appendChild(
                        document.createTextNode(tmpl.render(**args))
                    )
            else:
                # Create HTML tag
                tag = document.createElement(elem)
                pn.appendChild(tag)

                convert(node[elem], dom, parent=tag)
    elif isinstance(node, list):
        [convert(subn, dom, parent=pn) for subn in node]
    elif isinstance(node, str):
        handle_textnode(pn, node)


class IratySiteConfig:
    """
    Holds the configuration for an iraty website
    """

    def __init__(self, cfg_path, args):
        self.path = cfg_path
        self.args = args
        self._oc = {}

    @property
    def c(self):
        return self._oc

    def exists(self):
        return self.path.is_file()

    def init(self):
        if self.exists() and self.args.restore_config:
            try:
                with open(self.path, 'rt') as fd:
                    self._oc = OmegaConf.load(fd)

                # Basic check
                for attr in ['icf_version', 'theme',
                             'output_path', 'ipfs_output',
                             'ipfs_maddr', 'ipfs_rps_name',
                             'http_serve_port']:
                    if attr not in self.c:
                        raise ValueError(f'Attribute {attr} missing from '
                                         f'config file {self.path}')
            except Exception:
                self._oc = self.from_args()
                self.sync()
        else:
            # Not restoring config, use from command-line args
            self._oc = self.from_args()
            self.sync()

    def from_args(self):
        return OmegaConf.create({
            'icf_version': 1,
            'theme': self.args.theme,
            'output_path': self.args.outdir,
            'ipfs_output': self.args.ipfsout,
            'ipfs_maddr': self.args.ipfsmaddr,
            'ipfs_rps_name': self.args.rps_name,
            'http_serve_port': self.args.httpport
        })

    def sync(self):
        with open(self.path, 'wt') as fd:
            OmegaConf.save(self.c, fd)


class Iraty:
    def __init__(self,
                 command,
                 input_path,
                 ipfs_client,
                 ipfs_node_cfg,
                 args):
        self.command = command
        self.iclient = ipfs_client
        self.ipfs_node_cfg = ipfs_node_cfg
        self.args = args
        self.input_path = input_path

        if self.input_path.is_dir():
            cfgpath = self.input_path.joinpath('.iraty.yaml')
        else:
            cfgpath = Path(os.getcwd()).joinpath('.iraty.yaml')

        self.sitecfg = IratySiteConfig(cfgpath, self.args)
        self.sitecfg.init()

        self.outdirp = Path(self.sitecfg.c.output_path)

    def start(self):
        if os.getenv('HOME') == str(self.outdirp):
            raise Exception('Not using HOME as output, dude')

        self.outdirp.mkdir(parents=True, exist_ok=True)

        if self.sitecfg.exists() and self.args.purge:
            for root, dirs, files in os.walk(self.outdirp):
                for file in files:
                    # Only purge html files
                    if file.endswith('.html'):
                        os.unlink(os.path.join(root, file))

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

    def process_file(self, path: Path, dirdest: Path = None, output=False):
        dom = html()
        try:
            theme_name = os.path.basename(self.sitecfg.c.theme)
            themedp = Path(pkg_resources.resource_filename(
                'iraty.themes',
                self.sitecfg.c.theme
            ))

            with open(str(path), 'rt') as fd:
                foc = OmegaConf.load(fd)

                if theme_name != 'null' and themedp.is_dir():
                    dest = self.outdirp.joinpath(f'{theme_name}.css')

                    if not dest.is_file():
                        # Copy the theme's main CSS
                        shutil.copy(
                            str(themedp.joinpath(f'{theme_name}.css')),
                            str(self.outdirp)
                        )

                    # Compute the CSS's relative path to the root output dir
                    if dirdest:
                        css_relp = os.path.relpath(
                            str(dest), start=str(dirdest))
                    else:
                        css_relp = f'{theme_name}.css'

                    # Reference the CSS in <head>
                    css_link = {
                        'link': {
                            '_rel': 'stylesheet',
                            '_type': 'text/css',
                            '_href': css_relp
                        }
                    }

                    if foc.get('head'):
                        foc.head.setdefault('..', css_link)
                    else:
                        foc = OmegaConf.merge(foc, {'head': css_link})

                convert(
                    OmegaConf.to_container(foc, resolve=True),
                    dom
                )
        except Exception:
            traceback.print_exc()
            return None

        if output:
            cid = None

            if self.sitecfg.c.ipfs_output or self.command == 'ipfs-deploy':
                out = self.output_dom(dom)
                cid = self.ipfs_add(out)

                if cid:
                    rps = self.get_target_rps()
                    if rps and self.args.pintoremote:
                        # Pin to remote service
                        self.ipfs_pinremote(rps, cid)

                    print(cid, file=sys.stdout)
            else:
                self.output_dom(dom, fd=sys.stdout)

            if cid:
                self.ipns_publish(cid)

        return dom

    def get_target_rps(self):
        rps = self.ipfs_node_cfg.get('ipfs_rps_default')

        if is_str(rps):
            return rps
        elif self.sitecfg.c.ipfs_rps_name:
            return self.sitecfg.c.ipfs_rps_name

    def find_closest_layout(self, fp: Path, root: Path):
        """
        Find the closest .layout.yaml file (hierarchy-wise) to
        the file referenced by fp.
        """
        current = fp.parent
        dirs = [current]

        while current != root:
            current = current.parent
            dirs.append(current)

        for dir in dirs:
            layoutp = dir.joinpath('.layout.yaml')

            if layoutp.is_file():
                # TODO: check that this is a valid yaml
                return layoutp

    def process_directory(self, path: Path):
        try:
            for root, dirs, files in os.walk(str(path)):
                rr = root.replace(str(path), '').lstrip(os.sep)

                for file in files:
                    fp = Path(root).joinpath(file)
                    layoutp = self.find_closest_layout(fp, path)

                    ddest = self.outdirp.joinpath(rr)
                    ddest.mkdir(parents=True, exist_ok=True)

                    if fp.name.startswith('.'):
                        # Ignore dot files (reserved)
                        continue

                    ldom, blocks = None, []
                    if layoutp:
                        # Parse the layout
                        ldom = self.process_file(layoutp, dirdest=ddest)

                        if ldom:
                            # Parse declared blocks

                            for node in ldom.iter():
                                if node.name.startswith('block_'):
                                    blocks.append(node)

                    def findblock(name):
                        for blk in blocks:
                            if blk.name == name:
                                return blk

                    if fp.name.endswith('.yaml') or fp.name.endswith('.yml'):
                        fname = file.replace('.yaml', '.html').replace(
                            '.yml', '.html')
                        dest = ddest.joinpath(fname)
                        dom = self.process_file(fp, dirdest=ddest)

                        if ldom and len(blocks) > 0:
                            for node in dom.iter():
                                if node.name.startswith('block_'):
                                    blk = findblock(node.name)

                                    if blk is None or blk.parentNode is None:
                                        continue

                                    # Replace the node
                                    blk.parentNode.replaceChild(
                                        node.firstChild, blk)

                        if ldom:
                            # Layout mode
                            self.output_dom(ldom, dest=dest)
                        elif dom:
                            self.output_dom(dom, dest=dest)
                    else:
                        # Copy other files
                        shutil.copy(fp, str(ddest))
        except Exception:
            traceback.print_exc()
        else:
            cid = None

            if self.sitecfg.c.ipfs_output or self.command == 'ipfs-deploy':
                cid = self.ipfs_add(str(self.outdirp))

                if cid:
                    rps = self.get_target_rps()
                    if rps and self.args.pintoremote:
                        # Pin to remote service
                        if self.ipfs_pinremote(rps, cid):
                            print(cid, file=sys.stdout)
                    else:
                        print(cid, file=sys.stdout)
            else:
                if self.args.httpserve or self.command == 'serve':
                    http_serve(self.outdirp,
                               port=self.sitecfg.c.http_serve_port)
                else:
                    for root, dirs, files in os.walk(str(self.outdirp)):
                        for file in files:
                            print(os.path.join(root, file), file=sys.stdout)

            if cid:
                self.ipns_publish(cid)

    def ipns_genkey(self, name: str, type: str = 'ed25519'):
        return self.iclient.key.gen(name, type)

    def ipns_publish(self, cid):
        pk_id = None
        kn = self.args.ipns_key_name
        kid = self.args.ipns_key_id

        if not kn and not kid:
            return

        res = self.iclient.key.list()

        if res and 'Keys' in res:
            for key in res['Keys']:
                name = key.get('Name')
                _id = key.get('Id')

                if (kn and name == kn) or (kid and kid == _id):
                    pk_id = _id
                    break
        else:
            raise Exception('Cannot list IPNS keys')

        if not pk_id and kn:
            key = self.ipns_genkey(kn)
            pk_id = key['Id']
        elif pk_id:
            # Publish
            for att in range(0, 3):
                try:
                    resp = self.iclient.name.publish(cid, key=pk_id)
                    key = resp['Name']

                    print(f'/ipns/{key}', file=sys.stdout)
                    break
                except Exception as err:
                    print(f'Error publishing to {pk_id}: {err}', file=sys.stderr)
        else:
            raise Exception('Inexistent key. Please specify a key name with --ipns-name')


def list_themes():
    themes_root = pkg_resources.resource_filename(
        'iraty.themes',
        ''
    )
    for root, dirs, files in os.walk(str(themes_root)):
        for dir in dirs:
            if dir.startswith('_'):
                continue

            if root == themes_root:
                print(dir)
            else:
                print('/'.join([os.path.basename(root), dir]))


def _get_resolver_docstring(name: str):
    try:
        fn = getattr(resolvers, name)
        return inspect.getfullargspec(fn)[0], fn.__doc__
    except AttributeError:
        return None, None


def list_resolvers():
    help = ''

    for name, rslv in BaseContainer._resolvers.items():
        sig, doc = _get_resolver_docstring(name)

        if doc:
            if sig:
                argl = ','.join(list(sig))
                help += f'=> {name}({argl}):\n {doc}\n'
            else:
                help += f'=> {name}: {doc}\n'

    if shutil.which('less'):
        p = subprocess.Popen(['less'], stdin=subprocess.PIPE)
        p.communicate(input=help.encode())
    else:
        print(help)


def iraty(args):
    config_dir = Path(appdirs.user_config_dir('iraty'))
    config_dir.mkdir(parents=True, exist_ok=True)
    nodes_config_dir = config_dir.joinpath('ipfs-nodes')
    nodes_config_dir.mkdir(parents=True, exist_ok=True)

    node_configure_default(config_dir, nodes_config_dir)

    command = args.cmd.pop()

    if command == 'list-themes':
        list_themes()
        sys.exit(0)

    elif command == 'list-resolvers':
        list_resolvers()
        sys.exit(0)

    elif command in ['node-config', 'nc']:
        cfg = node_configure(args, config_dir, nodes_config_dir)

        if not cfg:
            print('Error configuring node', file=sys.stderr)
            sys.exit(1)

        print('Connect to IPFS node and register '
              'remote pinning services ? [y/n]')

        resp = sys.stdin.readline().strip()

        if resp.lower() == 'y':
            # Register configured pinning services
            try:
                count = 0
                ic = ipfshttpclient.connect(cfg.ipfs_api_maddr)

                services = ic.pinremote.service_ls()
                csrvs = [c['Service'] for c in services['RemoteServices']]

                for name, rpsc in cfg.ipfs_rps_cfg.items():
                    ep, key = rpsc.get('endpoint'), rpsc.get('key')

                    if is_str(key) and name not in csrvs:
                        print(f'=> Adding RPS: {name} (endpoint: {ep})')

                        ic.pinremote.service_add(
                            name, ep, key
                        )

                        count += 1

                print(f'=> Registered {count} service(s)')
            except Exception as err:
                print(f'Error configuring remote pinning: {err}',
                      file=sys.stderr)
                sys.exit(1)

        sys.exit(0)

    if len(args.input) != 1:
        print('Invalid input arguments', file=sys.stderr)
        sys.exit(1)

    ncp, node_cfg = node_get_config(nodes_config_dir, args.ipfs_node)

    if not node_cfg:
        print(f'Unconfigured IPFS node: {args.ipfs_node}', file=sys.stderr)
        sys.exit(1)

    filein = args.input[0]

    try:
        maddr = args.ipfsmaddr if args.ipfsmaddr else node_cfg.ipfs_api_maddr
        iclient = ipfshttpclient.connect(maddr)
    except Exception as err:
        # Should be fatal ?
        iclient = None
        print(f'IPFS connection Error: {err}', file=sys.stderr)
    else:
        # Set global client
        resolvers.ipfs_client = iclient

    input_path = Path(filein)
    ira = Iraty(command, input_path, iclient, node_cfg, args)
    ira.start()

    if not input_path.exists():
        print(f'{input_path} does not exist', file=sys.stderr)
        sys.exit(1)

    if input_path.is_file():
        resolvers.root_input_path = input_path.parent
        jenv.loader = FileSystemLoader(str(input_path.parent))
        ira.process_file(input_path, output=True)
    elif input_path.is_dir():
        resolvers.root_input_path = input_path
        jenv.loader = FileSystemLoader(str(input_path))
        ira.process_directory(input_path)
