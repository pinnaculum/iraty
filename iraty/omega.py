from omegaconf import DictConfig
from omegaconf import ListConfig


def shove(target, c, pos='last'):
    dst = None

    if isinstance(target, DictConfig):
        if '...' not in target:
            target['...'] = []

        dst = target['...']
    elif isinstance(target, ListConfig):
        dst = target
    else:
        return

    if pos == 'last':
        dst.append(c)
    elif pos == 'first':
        dst.insert(0, c)
